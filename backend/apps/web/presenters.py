"""
What the applicant pages show, worked out on the server. Templates only display
these values — no fee arithmetic or status rules live in the browser.
"""
from dataclasses import dataclass, field

from django.conf import settings as dj_settings

from apps.admissions.discounts import first_installment
from apps.admissions.models import Application, AwardRequest
from apps.core.models import SiteSettings
from apps.payments.models import Payment

TRACKER = ["Applied", "Admission", "Programme fee", "Enrolled"]
STAGE = {Application.Status.PENDING: 1, Application.Status.AWAITING_VERIFICATION: 1,
         Application.Status.ADMITTED: 2, Application.Status.ENROLLED: 4, Application.Status.REJECTED: 1}


def payer_charge() -> int:
    return dj_settings.ZAINPAY["PAYER_CHARGE"]


def tracker(app: Application) -> list[dict]:
    """[{label, state: done|current|bad|''}] for the progress line."""
    idx, rejected = STAGE.get(app.status, 1), app.status == Application.Status.REJECTED
    steps = []
    for i, label in enumerate(TRACKER):
        bad = rejected and i == 1
        state = "bad" if bad else "done" if i < idx else "current" if (not rejected and i == idx) else ""
        steps.append({"n": i + 1, "label": "Not admitted" if bad else label, "state": state})
    return steps


def application_fee_due(app: Application) -> int:
    """The application-fee part of amount_payable (0 if it was paid separately and credited)."""
    return max(0, app.amount_payable - (app.fee - app.discount_amount))


def award_of(app):
    return getattr(app, "award_request", None)


def latest_receipt(app: Application):
    return (app.payments.filter(kind=Payment.Kind.CHARGE, purpose=Payment.Purpose.PROGRAMME_FEE,
                                status=Payment.Status.SUCCESS).order_by("-verified_at").first())


def installments_allowed() -> bool:
    return SiteSettings.load().allow_installments


@dataclass
class PayOptions:
    """Everything the invoice shows and the amounts each choice will charge."""

    full: int
    half: int | None          # 1st installment, when the payer may split
    balance: int              # programme fee still owed after a 1st installment
    is_balance: bool
    charge: int = field(default_factory=payer_charge)

    def due(self, plan: str) -> int:
        if self.is_balance:
            return self.balance
        return self.half if plan == "half" and self.half else self.full

    @property
    def due_full(self) -> int:
        """What "pay in full" (or the balance) costs now."""
        return self.due("full")

    @property
    def balance_after_half(self) -> int:
        return self.full - self.half if self.half else 0


def pay_options(app: Application) -> PayOptions:
    is_balance = app.payment_status == Application.PaymentStatus.PART_PAID
    half = None
    if not is_balance and app.status == Application.Status.ADMITTED and app.amount_paid == 0 and installments_allowed():
        half = first_installment(app)
    return PayOptions(full=app.amount_payable, half=half, balance=app.balance, is_balance=is_balance)


def next_step(app: Application) -> dict:
    """The call to action on My applications: {kind, …} rendered by the template."""
    award = award_of(app)
    if app.status == Application.Status.AWAITING_VERIFICATION:
        return {"kind": "verify"}
    if app.status == Application.Status.REJECTED:
        return {"kind": "rejected"}
    if app.status == Application.Status.ADMITTED:
        opts = pay_options(app)
        return {"kind": "pay", "opts": opts,
                "award_approved": award is not None and award.status == AwardRequest.Status.APPROVED,
                "award_declined": award is not None and award.status == AwardRequest.Status.REJECTED,
                "app_fee": application_fee_due(app)}
    if app.status == Application.Status.ENROLLED:
        enrollment = getattr(app, "enrollment", None)
        return {"kind": "enrolled", "student_no": enrollment.student.student_no if enrollment else "",
                "student_pk": enrollment.student_id if enrollment else None,
                "part_paid": app.payment_status == Application.PaymentStatus.PART_PAID,
                "receipt": latest_receipt(app)}
    return {"kind": "processing"}


def receipt_lines(payment: Payment) -> list[tuple[str, str, bool]]:
    """Itemised rows for a receipt: (label, naira text, is_negative)."""
    def n(v):
        return f"₦{v:,}"

    if payment.installment == Payment.Installment.FIRST:
        return [("Payment", "1st installment (50% of the programme fee + application fee)", False)]
    if payment.installment == Payment.Installment.BALANCE:
        return [("Payment", "Balance of the programme fee", False)]
    if not payment.fee or payment.fee == payment.amount:
        return []
    discount = payment.discount or 0
    app_fee = payment.amount - (payment.fee - discount)
    if app_fee < 0:  # (older records) discount implied by the amount
        return [("Programme fee", n(payment.fee), False), ("Discount applied", "−" + n(payment.fee - payment.amount), True)]
    rows = [("Programme fee", n(payment.fee), False)]
    if discount:
        rows.append(("Discount applied", "−" + n(discount), True))
    if app_fee:
        rows.append(("Application fee", n(app_fee), False))
    return rows


def paid_for(payment: Payment) -> str:
    if payment.purpose == Payment.Purpose.APPLICATION_FEE:
        return "Application fee"
    return {Payment.Installment.FIRST: "Programme fee — 1st installment",
            Payment.Installment.BALANCE: "Programme fee — balance"}.get(payment.installment, "Programme fee")
