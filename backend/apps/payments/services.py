"""
Payment lifecycle, independent of the gateway:

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
from apps.admissions.services import mark_paid, mark_payment_failed, requote_for_payment
from apps.core.exceptions import ServiceError
from apps.core.models import Sequence, SiteSettings

from .gateways import FAILED, SUCCESS, GatewayError, VerifyResult, get_gateway
from .models import Payment

logger = logging.getLogger(__name__)


def new_reference(settings: SiteSettings) -> str:
    """TSCE-ZP-20261001-000001"""
    return f"{settings.payment_ref_prefix}-{today():%Y%m%d}-{Sequence.next('tx'):06d}"


def start_checkout(app: Application, callback_url: str) -> Payment:
    if app.payment_status == Application.PaymentStatus.PAID:
        raise ServiceError("This application has already been paid.", "already_paid")
    if app.status == Application.Status.REJECTED:
        raise ServiceError("This application was not successful, so it can't be paid.", "application_rejected")

    gateway = get_gateway()
    with transaction.atomic():
        settings = SiteSettings.load()
        app = requote_for_payment(Application.objects.select_related("programme", "cohort", "user").get(pk=app.pk), settings)
        if seats_taken(app.cohort).get(app.programme_id, 0) >= app.programme.capacity:
            raise ServiceError(f"Sorry — {app.programme.name} is now full for the {app.cohort.name}. "
                               "Contact admissions to change programme.", "programme_full")
        payment = Payment.objects.create(
            reference=new_reference(settings), kind=Payment.Kind.CHARGE, application=app, user=app.user,
            name=app.full_name, email=app.email,
            description=f"{app.programme.name} — tuition ({app.cohort.name})",
            amount=app.amount_payable, fee=app.fee, discount=app.discount_amount,
            status=Payment.Status.PENDING, gateway=gateway.name,
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
        if result.status == SUCCESS:
            payment.status = Payment.Status.SUCCESS
            payment.verified_at = timezone.now()
            payment.channel = result.channel or payment.channel
            payment.failure_reason = ""
            payment.save()
            if payment.application_id:
                mark_paid(payment.application, payment)
        elif result.status == FAILED and payment.status == Payment.Status.PENDING:
            payment.status = Payment.Status.FAILED
            payment.failure_reason = result.failure_reason[:300]
            payment.save()
            if payment.application_id:
                mark_payment_failed(payment.application, payment)
        else:
            payment.save(update_fields=["gateway_payload", "updated_at"])
    return payment


def process_payment(payment: Payment) -> Payment:
    """Asks the gateway the payment was made with, then records the answer. Raises GatewayError."""
    if payment.status in (Payment.Status.SUCCESS, Payment.Status.REFUNDED):
        return payment
    result = get_gateway(payment.gateway).verify(payment.reference)
    return apply_result(payment, result)
