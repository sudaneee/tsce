"""
Admissions business rules (revised flow, 1 Oct 2026):

    create_application()        signed-in, email-verified account applies (for self or a child)
                                → admitted at once, or AWAITING_VERIFICATION for an award request
    review_award()              staff verify the WAEC result in person → admit() at 50% or full price
    sync_programme_quote()      re-price at checkout (early bird by payment date; application fee added)
    programme_fee_paid()        → ENROLLED: Student record, student number, Enrollment, seat taken

Since 4 Oct 2026 there is no separate application-fee payment: the ₦5,000 is added
to the programme fee. application_fee_paid() remains only for payments started
under the earlier flow; those applicants are credited.

Views stay thin and call these; every change of state happens inside a
transaction and leaves a line in the application history.
"""
from django.conf import settings as dj_settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.comms.models import Notification
from apps.comms.services import notify, notify_staff
from apps.core.exceptions import ServiceError
from apps.core.models import Sequence, SiteSettings

from .discounts import admissions_state, excellence_eligible, programme_quote, seats_taken, today
from .models import Application, ApplicationEvent, AwardRequest

MY_APPLICATIONS = "pages/my-applications.html"


def naira(amount):
    return f"₦{amount:,}"


def _event(app, text, ok=False, actor=None):
    ApplicationEvent.objects.create(application=app, text=text, ok=ok, actor=actor)


@transaction.atomic
def create_application(data, user) -> Application:
    if not user.can_apply:
        raise ServiceError("Staff accounts can't apply. Sign out and use a student or parent account.", "staff_account")
    if user.needs_email_verification:
        raise ServiceError("Please verify your email address before applying.", "email_unverified")

    settings = SiteSettings.load()
    state = admissions_state(settings)
    if not state.open:
        raise ServiceError(state.message, "admissions_closed")

    cohort = settings.current_cohort
    programme = data["programmeId"]
    if seats_taken(cohort).get(programme.pk, 0) >= programme.capacity:
        raise ServiceError(f"{programme.name} is full for the {cohort.name}. Please choose another programme.",
                           "programme_full", field="programmeId")

    wants_award = data["awardRequest"] == AwardRequest.Type.EXCELLENCE
    if wants_award and not excellence_eligible(settings, data["waecStatus"], data["waecYear"], data["numAs"]):
        raise ServiceError(
            f"The Excellence Award needs WAEC/NECO from {settings.excellence_min_waec_year} or later "
            f"with at least {settings.excellence_min_as} A's.", "not_eligible", field="awardRequest",
        )

    # A self-applicant applies as themselves; a parent enters each child's details.
    email = data["email"] if user.role == User.Role.PARENT else user.email
    first, last = data["firstName"].strip(), data["lastName"].strip()
    existing = (Application.objects.filter(user=user, first_name__iexact=first, last_name__iexact=last, dob=data["dob"],
                                           programme=programme, cohort=cohort)
                .exclude(status=Application.Status.REJECTED).first())
    if existing:
        raise ServiceError(
            f"{first} {last} already has an application for {programme.name} ({existing.number}).",
            "duplicate_application", extra={"applicationId": existing.number},
        )

    q = programme_quote(Application(programme=programme, cohort=cohort, application_fee=settings.application_fee), settings)
    app = Application.objects.create(
        number=f"TSCE/APP/{today().year}/{Sequence.next('app'):05d}",
        user=user,
        first_name=first, middle_name=data["middleName"].strip(), last_name=last,
        gender=data["gender"], dob=data["dob"], phone=data["phone"], email=email,
        address=data["address"].strip(), state=data["state"], lga=data["lga"].strip(),
        qualification=data["qualification"], institution=data["institution"].strip(), grad_year=data["gradYear"],
        waec_status=data["waecStatus"], waec_year=data["waecYear"], num_as=data["numAs"] or 0,
        waec_file=data.get("resultFile") or "",
        programme=programme, cohort=cohort, schedule=data["schedule"],
        application_fee=settings.application_fee,
        fee=q.fee, discount_type=q.discount_type, discount_pct=q.discount_pct,
        discount_amount=q.discount_amount, amount_payable=q.amount_payable,
    )
    _event(app, "Application submitted online", actor=user)
    if wants_award:
        AwardRequest.objects.create(
            application=app, type=AwardRequest.Type.EXCELLENCE, requested_pct=settings.excellence_pct,
            evidence=f"WAEC {app.waec_year} — {app.num_as} A's (declared{', result uploaded' if app.waec_file else ''})",
        )
        _event(app, "Excellence Award requested — result to be verified in person", actor=user)

    if settings.staff_application_alerts:
        notify_staff("New application", f"{app.full_name} applied for {programme.name}.", Notification.Type.APPLICATION)
    if wants_award:
        return await_verification(app)
    return admit(app)


def await_verification(app: Application) -> Application:
    """Excellence Award requested: admission waits for the school to see the original result."""
    app.status = Application.Status.AWAITING_VERIFICATION
    app.save(update_fields=["status", "updated_at"])
    notify(app.user, "Bring the WAEC/NECO result to TSCE",
           f"The application {app.number} for {app.full_name} ({app.programme.name}) has been received. To confirm the "
           f"Excellence Award, please visit TSCE ({SiteSettings.load().address}) with the original WAEC/NECO result. "
           "Admission is confirmed after verification, and you can then pay the programme fee in the portal.",
           Notification.Type.SCHOLARSHIP, link=MY_APPLICATIONS, email=True)
    notify_staff("Excellence Award to verify", f"{app.full_name} ({app.number}) will bring a WAEC/NECO result for verification.",
                 Notification.Type.SCHOLARSHIP)
    return app


def admit(app: Application, actor=None) -> Application:
    """Admission approved: price the programme fee and invite payment."""
    settings = SiteSettings.load()
    q = programme_quote(app, settings)
    app.discount_type, app.discount_pct = q.discount_type, q.discount_pct
    app.discount_amount, app.amount_payable = q.discount_amount, q.amount_payable
    app.status = Application.Status.ADMITTED
    app.save()
    _event(app, "Admission approved" + (" by the admissions office" if actor else " automatically"), ok=True, actor=actor)
    fee_note = f" (includes the {naira(q.application_fee)} application fee)" if q.application_fee else ""
    notify(app.user, "Admission approved",
           f"Congratulations! {app.full_name} has been admitted to {app.programme.name} ({app.cohort.name}). "
           f"Pay the programme fee of {naira(app.amount_payable)}{fee_note} to secure {'the' if app.user.role == User.Role.PARENT else 'your'} seat.",
           Notification.Type.APPLICATION, link=MY_APPLICATIONS, email=True)
    return app


def application_fee_paid(app: Application, payment) -> Application:
    """Verified application-fee payment. Call inside the transaction that confirmed the payment."""
    app = Application.objects.select_related("user", "programme", "cohort").get(pk=app.pk)
    if app.application_fee_paid_at:
        _flag_duplicate(app, payment, "application fee")
        return app
    app.application_fee_paid_at = payment.verified_at or timezone.now()
    app.save(update_fields=["application_fee_paid_at", "updated_at"])
    _event(app, f"Application fee of {naira(payment.amount)} paid ({payment.reference}) — credited against the programme fee", ok=True)

    if app.status != Application.Status.PENDING:
        # Already admitted under the single-payment flow: just credit it.
        sync_programme_quote(app, SiteSettings.load())
        return app
    award = getattr(app, "award_request", None)
    if award and award.status == AwardRequest.Status.PENDING:
        app.status = Application.Status.AWAITING_VERIFICATION
        app.save(update_fields=["status", "updated_at"])
        notify(app.user, "Bring the WAEC/NECO result to TSCE",
               f"The application fee for {app.full_name} is paid. To confirm the Excellence Award, please visit TSCE "
               f"({SiteSettings.load().address}) with the original WAEC/NECO result. Admission is confirmed after "
               "verification, and you can then pay the programme fee in the portal.",
               Notification.Type.SCHOLARSHIP, link=MY_APPLICATIONS, email=True)
        notify_staff("Excellence Award to verify", f"{app.full_name} ({app.number}) will bring a WAEC/NECO result for verification.",
                     Notification.Type.SCHOLARSHIP)
        return app
    return admit(app)


@transaction.atomic
def review_award(app: Application, approve: bool, staff_user, note: str = "") -> Application:
    """Staff decision after seeing the result in person. Either way the applicant is admitted."""
    app = Application.objects.select_related("user", "programme", "cohort", "award_request").select_for_update().get(pk=app.pk)
    award = getattr(app, "award_request", None)
    if award is None or award.status != AwardRequest.Status.PENDING:
        raise ServiceError("There is no pending award request on this application.", "no_pending_award")
    if app.status != Application.Status.AWAITING_VERIFICATION:
        raise ServiceError("This application isn't waiting for award verification.", "not_awaiting_verification")

    settings = SiteSettings.load()
    award.status = AwardRequest.Status.APPROVED if approve else AwardRequest.Status.REJECTED
    award.awarded_pct = settings.excellence_pct if approve else None
    award.reviewed_by, award.reviewed_at, award.note = staff_user, timezone.now(), note[:300]
    award.save()
    _event(app, f"Excellence Award {'approved' if approve else 'not approved'} after result verification"
                + (f" — {note}" if note else ""), ok=approve, actor=staff_user)
    notify(app.user, "Excellence Award " + ("approved" if approve else "decision"),
           f"The Excellence Award for {app.full_name} was "
           + (f"approved: {settings.excellence_pct}% off the programme fee." if approve
              else "not approved, so the normal programme fee applies.")
           + (f" Note from admissions: {note}" if note else ""),
           Notification.Type.SCHOLARSHIP, link=MY_APPLICATIONS)
    return admit(app, actor=staff_user)


def sync_programme_quote(app: Application, settings: SiteSettings) -> Application:
    """Re-price at checkout: the early bird depends on the PAYMENT date; an approved award never changes."""
    q = programme_quote(app, settings)
    if q.amount_payable != app.amount_payable or q.discount_type != app.discount_type:
        old = app.amount_payable
        app.discount_type, app.discount_pct = q.discount_type, q.discount_pct
        app.discount_amount, app.amount_payable = q.discount_amount, q.amount_payable
        app.save(update_fields=["discount_type", "discount_pct", "discount_amount", "amount_payable", "updated_at"])
        _event(app, f"Programme fee re-priced at payment: {naira(old)} → {naira(app.amount_payable)}")
    return app


def _find_or_create_student(app: Application):
    from apps.academics.models import Student

    account = app.user
    if account.role == User.Role.PARENT:
        student = Student.objects.filter(guardian=account, first_name__iexact=app.first_name,
                                         last_name__iexact=app.last_name, dob=app.dob).first()
        owner = {"guardian": account}
    else:
        student = Student.objects.filter(user=account).first()
        owner = {"user": account}
    if student:
        return student
    return Student.objects.create(
        **owner, student_no=f"TSCE/{today().year}/{Sequence.next('student'):05d}",
        first_name=app.first_name, middle_name=app.middle_name, last_name=app.last_name, gender=app.gender,
        dob=app.dob, phone=app.phone, email=app.email, address=app.address, state=app.state, lga=app.lga,
        qualification=app.qualification, institution=app.institution,
    )


def programme_fee_paid(app: Application, payment) -> Application:
    """Verified programme-fee payment → enrolled. Call inside the transaction that confirmed the payment."""
    from apps.academics.models import Enrollment

    app = Application.objects.select_related("user", "programme", "cohort").get(pk=app.pk)
    if app.payment_status == Application.PaymentStatus.PAID:
        _flag_duplicate(app, payment, "programme fee")
        return app

    student = _find_or_create_student(app)
    if app.user.role == User.Role.APPLICANT:
        app.user.role = User.Role.STUDENT
        app.user.save(update_fields=["role"])

    app.status = Application.Status.ENROLLED
    app.payment_status = Application.PaymentStatus.PAID
    app.paid_at = payment.verified_at or timezone.now()
    app.save(update_fields=["status", "payment_status", "paid_at", "updated_at"])
    Enrollment.objects.create(
        student=student, application=app, programme=app.programme, cohort=app.cohort, schedule=app.schedule,
        start_date=app.cohort.start_date, end_date=app.programme.end_date_from(app.cohort.start_date),
        status=Enrollment.Status.ACTIVE, amount_paid=payment.amount,
    )
    _event(app, f"Programme fee of {naira(payment.amount)} paid ({payment.reference})", ok=True)
    _event(app, f"Enrolled as {student.student_no}", ok=True)

    start = app.cohort.start_date
    notify(app.user, "Enrolment confirmed",
           f"{app.full_name} is enrolled in {app.programme.name}. Student number: {student.student_no}. "
           f"Classes for the {app.cohort.name} begin on {start.day} {start:%B %Y}. Receipt: {payment.reference}.",
           Notification.Type.PAYMENT, link=MY_APPLICATIONS, email=True)
    if SiteSettings.load().staff_payment_alerts:
        notify_staff("Programme fee received", f"{app.full_name} paid {naira(payment.amount)} for {app.programme.name}.",
                     Notification.Type.PAYMENT)
    return app


def payment_failed(app: Application, payment) -> None:
    from apps.payments.models import Payment

    if payment.purpose == Payment.Purpose.PROGRAMME_FEE and app.payment_status == Application.PaymentStatus.UNPAID:
        Application.objects.filter(pk=app.pk).update(payment_status=Application.PaymentStatus.FAILED)
    _event(app, f"{payment.get_purpose_display()} payment attempt failed ({payment.reference})")


def _flag_duplicate(app, payment, what):
    """Two checkouts both completed (e.g. two tabs). Keep the money on record and flag it for refund."""
    _event(app, f"Duplicate {what} payment {payment.reference} ({naira(payment.amount)}) received — refund required")
    notify_staff("Duplicate payment — refund needed",
                 f"{app.full_name} paid the {what} twice for {app.number}. Refund {payment.reference} ({naira(payment.amount)}).",
                 Notification.Type.PAYMENT)


@transaction.atomic
def reject_application(app: Application, staff_user, note: str) -> Application:
    """Staff decision. Enrolled students are withdrawn through the student record, not here."""
    app = Application.objects.select_related("user", "programme").get(pk=app.pk)
    if app.status in (Application.Status.ENROLLED, Application.Status.REJECTED):
        raise ServiceError(f"An application that is {app.status.lower()} can't be rejected.", "invalid_state")
    app.status = Application.Status.REJECTED
    app.save(update_fields=["status", "updated_at"])
    award = getattr(app, "award_request", None)
    if award and award.status == AwardRequest.Status.PENDING:
        award.status, award.reviewed_by, award.reviewed_at = AwardRequest.Status.REJECTED, staff_user, timezone.now()
        award.note = "Application not successful"
        award.save()
    _event(app, "Application not successful" + (f" — {note}" if note else ""), actor=staff_user)
    notify(app.user, "Application update",
           f"We're sorry — the application {app.number} for {app.full_name} ({app.programme.name}) was not successful."
           + (f" Reason: {note}" if note else "") + " The application fee is non-refundable.",
           Notification.Type.APPLICATION, link=MY_APPLICATIONS, email=True)
    return app


def send_reminder(app: Application, staff_user) -> str:
    """Nudge the account holder about the next payment due. Returns what was reminded."""
    charge = dj_settings.ZAINPAY["PAYER_CHARGE"]
    if app.status == Application.Status.ADMITTED:
        what, amount = "programme fee", app.amount_payable
    else:
        raise ServiceError("There is no payment due on this application.", "nothing_due")
    notify(app.user, f"Reminder: {what} due",
           f"The {what} of {naira(amount + charge)} for {app.full_name} ({app.programme.name}) is still due. "
           "Pay it from My applications" + (" to secure the seat — places are limited." if what == "programme fee" else "."),
           Notification.Type.PAYMENT, link=MY_APPLICATIONS, email=True)
    _event(app, f"Payment reminder sent ({what})", actor=staff_user)
    return what
