"""
Payment lifecycle, independent of the gateway. Two purposes per application:
the APPLICATION FEE (first) and the PROGRAMME FEE (after admission).

    start_checkout()  → Payment(PENDING) + hosted checkout URL
    process_payment() → ask the gateway, then apply_result() exactly once

A payment is confirmed by whichever arrives first — the browser coming back
(callback), the Zainpay webhook, the payer pressing "Check status", or the
reconcile_payments cron job. apply_result() is idempotent, so the others are
no-ops. The gateway is never called inside a database transaction: SQLite has
one writer, and a 30-second network call must not hold the lock.
"""
import logging

from django.db import transaction
from django.utils import timezone

from apps.admissions.discounts import seats_taken, today
from apps.admissions.models import Application
from apps.admissions.services import application_fee_paid, payment_failed, programme_fee_paid, sync_programme_quote
from apps.core.exceptions import ServiceError
from apps.core.models import Sequence, SiteSettings

from .gateways import FAILED, SUCCESS, GatewayError, VerifyResult, get_gateway
from .models import Payment

logger = logging.getLogger(__name__)


def new_reference(settings: SiteSettings) -> str:
    """TSCE-ZP-20261001-000001"""
    return f"{settings.payment_ref_prefix}-{today():%Y%m%d}-{Sequence.next('tx'):06d}"


def _checkout_terms(app: Application, purpose: str, settings: SiteSettings) -> dict:
    """What is being paid now, or a ServiceError saying why it can't be."""
    if app.status == Application.Status.REJECTED:
        raise ServiceError("This application was not successful, so it can't be paid.", "application_rejected")
    if purpose == Payment.Purpose.APPLICATION_FEE:
        if app.application_fee_paid_at:
            raise ServiceError("The application fee has already been paid.", "already_paid")
        return {"amount": app.application_fee, "fee": app.application_fee, "discount": 0,
                "description": f"Application fee — {app.programme.name} ({app.cohort.name})"}

    if app.payment_status == Application.PaymentStatus.PAID:
        raise ServiceError("The programme fee has already been paid.", "already_paid")
    if app.status != Application.Status.ADMITTED:
        msg = {
            Application.Status.PENDING: "Pay the application fee first.",
            Application.Status.AWAITING_VERIFICATION: "The Excellence Award must be verified at TSCE before the programme fee can be paid.",
        }.get(app.status, "This application can't take a programme-fee payment.")
        raise ServiceError(msg, "not_admitted")
    sync_programme_quote(app, settings)
    if seats_taken(app.cohort).get(app.programme_id, 0) >= app.programme.capacity:
        raise ServiceError(f"Sorry — {app.programme.name} is now full for the {app.cohort.name}. "
                           "Contact admissions to change programme.", "programme_full")
    return {"amount": app.amount_payable, "fee": app.fee, "discount": app.discount_amount,
            "description": f"{app.programme.name} — programme fee ({app.cohort.name})"}


def start_checkout(app: Application, purpose: str, callback_url: str) -> Payment:
    if purpose not in Payment.Purpose.values:
        raise ServiceError("Unknown payment type.", "invalid")
    gateway = get_gateway()
    with transaction.atomic():
        settings = SiteSettings.load()
        app = Application.objects.select_related("programme", "cohort", "user", "award_request").get(pk=app.pk)
        terms = _checkout_terms(app, purpose, settings)
        payment = Payment.objects.create(
            reference=new_reference(settings), kind=Payment.Kind.CHARGE, purpose=purpose, application=app,
            user=app.user, name=app.full_name, email=app.user.email, status=Payment.Status.PENDING,
            gateway=gateway.name, **terms,
        )

    try:
        url = gateway.initialize(payment, callback_url, mobile=app.phone.replace(" ", ""))
    except GatewayError as exc:
        logger.error("Checkout init failed for %s: %s", app.number, exc)
        Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.FAILED, failure_reason=str(exc)[:300])
        raise ServiceError("We couldn't start the payment just now. Please try again in a moment.",
                           "gateway_unavailable", status_code=502)
    payment.checkout_url = url
    payment.save(update_fields=["checkout_url", "updated_at"])
    return payment


def apply_result(payment: Payment, result: VerifyResult) -> Payment:
    """Records a gateway answer. Idempotent: a confirmed payment is never changed again."""
    with transaction.atomic():
        payment = Payment.objects.select_related("application").get(pk=payment.pk)  # fresh, under the write lock
        if payment.status in (Payment.Status.SUCCESS, Payment.Status.REFUNDED):
            return payment
        payment.gateway_payload = {**(payment.gateway_payload or {}), "verify": result.raw}
        if result.status == SUCCESS and result.deposited is not None and result.deposited < payment.amount:
            # Bank transfers can arrive short. Never give value for less than the fee.
            if payment.status == Payment.Status.PENDING:
                payment.status = Payment.Status.FAILED
                payment.failure_reason = (f"Underpaid: received {result.deposited:,.0f}, "
                                          f"expected {payment.amount:,} (+ Zainpay charge)")
                payment.save()
                _flag_underpayment(payment)
            else:
                payment.save(update_fields=["gateway_payload", "updated_at"])
        elif result.status == SUCCESS:
            payment.status = Payment.Status.SUCCESS
            payment.verified_at = timezone.now()
            payment.channel = result.channel or payment.channel
            payment.failure_reason = ""
            payment.save()
            if payment.application_id:
                if payment.purpose == Payment.Purpose.APPLICATION_FEE:
                    application_fee_paid(payment.application, payment)
                else:
                    programme_fee_paid(payment.application, payment)
        elif result.status == FAILED and payment.status == Payment.Status.PENDING:
            payment.status = Payment.Status.FAILED
            payment.failure_reason = result.failure_reason[:300]
            payment.save()
            if payment.application_id:
                payment_failed(payment.application, payment)
        else:
            payment.save(update_fields=["gateway_payload", "updated_at"])
    return payment


def _flag_underpayment(payment: Payment):
    from apps.admissions.models import ApplicationEvent
    from apps.comms.models import Notification
    from apps.comms.services import notify_staff

    if payment.application_id:
        ApplicationEvent.objects.create(application=payment.application, text=f"Payment {payment.reference} not accepted — {payment.failure_reason}")
    notify_staff("Underpayment — follow up", f"{payment.name}: {payment.failure_reason}. Ref {payment.reference}.",
                 Notification.Type.PAYMENT)


def process_payment(payment: Payment) -> Payment:
    """Asks the gateway the payment was made with, then records the answer. Raises GatewayError."""
    if payment.status in (Payment.Status.SUCCESS, Payment.Status.REFUNDED):
        return payment
    result = get_gateway(payment.gateway).verify(payment.reference)
    return apply_result(payment, result)


def counted_charge_ids(application_ids=None) -> set[int]:
    """
    For each application and fee, the charge that actually paid it (the first
    to succeed). Any later successful charge for the same fee is a duplicate.
    """
    qs = Payment.objects.filter(kind=Payment.Kind.CHARGE, application__isnull=False,
                                status__in=[Payment.Status.SUCCESS, Payment.Status.REFUNDED])
    if application_ids is not None:
        qs = qs.filter(application_id__in=application_ids)
    first = {}
    for pid, app_id, purpose in qs.order_by("verified_at", "id").values_list("id", "application_id", "purpose"):
        first.setdefault((app_id, purpose), pid)
    return set(first.values())


def is_duplicate(payment: Payment) -> bool:
    return (payment.kind == Payment.Kind.CHARGE and payment.status == Payment.Status.SUCCESS
            and payment.application_id is not None
            and payment.pk not in counted_charge_ids([payment.application_id]))


def refund_duplicate(payment: Payment, staff_user, transfer_ref: str, note: str = "") -> Payment:
    """
    Records a refund the bursar has made by bank transfer. Fees are non-refundable,
    so only duplicate payments qualify. Returns the refund record.
    """
    from apps.admissions.models import ApplicationEvent
    from apps.admissions.services import naira
    from apps.comms.models import Notification
    from apps.comms.services import notify

    with transaction.atomic():
        payment = Payment.objects.select_related("application__user").get(pk=payment.pk)
        if payment.status != Payment.Status.SUCCESS or not is_duplicate(payment):
            raise ServiceError("Only duplicate payments can be refunded — application and programme fees are "
                               "otherwise non-refundable.", "not_refundable")
        now = timezone.now()
        refund = Payment.objects.create(
            reference=f"{payment.reference}-RF", kind=Payment.Kind.REFUND, purpose=payment.purpose, parent=payment,
            application=payment.application, user=payment.user, name=payment.name, email=payment.email,
            description=f"Refund of duplicate payment {payment.reference}", amount=payment.amount,
            status=Payment.Status.SUCCESS, gateway="manual", gateway_ref=transfer_ref[:100],
            gateway_payload={"note": note[:300]}, verified_at=now, verified_by=staff_user,
        )
        payment.status, payment.refunded_at = Payment.Status.REFUNDED, now
        payment.save(update_fields=["status", "refunded_at", "updated_at"])
        app = payment.application
        ApplicationEvent.objects.create(application=app, actor=staff_user, ok=True,
                                        text=f"Duplicate payment {payment.reference} refunded ({naira(payment.amount)}, transfer ref {transfer_ref})")
    notify(app.user, "Refund sent",
           f"We've refunded {naira(payment.amount)} for the duplicate payment {payment.reference} ({app.full_name}). "
           f"Bank transfer reference: {transfer_ref}.", Notification.Type.PAYMENT, email=True)
    return refund
