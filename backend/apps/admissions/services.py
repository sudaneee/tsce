"""
Admissions business rules. Views stay thin and call these; every change of
state happens inside a transaction and leaves a line in the application history.
"""
from django.db import transaction

from apps.accounts.models import User
from apps.comms.models import Notification
from apps.comms.services import notify, notify_staff
from apps.core.exceptions import ServiceError
from apps.core.models import Sequence, SiteSettings

from .discounts import admissions_state, excellence_eligible, quote, seats_taken, today
from .models import Application, ApplicationEvent, AwardRequest


def _resolve_applicant(data, request_user):
    """
    Who is applying. Signed-in users apply as themselves. Visitors get a new
    applicant account, or — if the email already has one — must give its password.
    """
    email = data["email"]
    if request_user and request_user.is_authenticated:
        if request_user.is_portal_staff:
            raise ServiceError("Staff accounts can't apply. Sign out and apply with a personal email.", "staff_account")
        if request_user.email != email:
            raise ServiceError(
                f"You're signed in as {request_user.email}. Apply with that email, or sign out first.",
                "email_mismatch", field="email",
            )
        return request_user

    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        return User.objects.create_user(
            email, data["password"], full_name=f'{data["firstName"]} {data["lastName"]}', role=User.Role.APPLICANT
        )
    if user.is_portal_staff:
        raise ServiceError("This email belongs to a TSCE staff account. Please use a personal email.", "staff_account", field="email")
    if not user.check_password(data["password"]):
        raise ServiceError(
            "An account with this email already exists. Enter the password you used before, or sign in first.",
            "account_exists", field="password",
        )
    if not user.is_active:
        raise ServiceError("This account has been disabled. Contact the TSCE admin office.", "account_disabled", field="email")
    return user


@transaction.atomic
def create_application(data, request_user=None) -> Application:
    settings = SiteSettings.load()
    state = admissions_state(settings)
    if not state.open:
        raise ServiceError(state.message, "admissions_closed")

    cohort = settings.current_cohort
    programme = data["programmeId"]
    if seats_taken(cohort).get(programme.pk, 0) >= programme.capacity:
        raise ServiceError(f"{programme.name} is full for the {cohort.name}. Please choose another programme.",
                           "programme_full", field="programmeId")

    award_type = data["awardRequest"] if data["awardRequest"] != "none" else ""
    eligible = excellence_eligible(settings, data["waecStatus"], data["waecYear"], data["numAs"])
    if award_type == AwardRequest.Type.EXCELLENCE and not eligible:
        raise ServiceError(
            f"The Excellence Award needs WAEC/NECO from {settings.excellence_min_waec_year} or later "
            f"with at least {settings.excellence_min_as} A's.", "not_eligible", field="awardRequest",
        )

    user = _resolve_applicant(data, request_user)

    existing = (Application.objects.filter(user=user, programme=programme, cohort=cohort)
                .exclude(status=Application.Status.REJECTED).first())
    if existing:
        raise ServiceError(
            f"You've already applied for {programme.name} ({existing.number}).", "duplicate_application",
            extra={"applicationId": existing.number, "paymentStatus": existing.payment_status},
        )

    q = quote(programme, cohort, settings)
    app = Application.objects.create(
        number=f"TSCE/APP/{today().year}/{Sequence.next('app'):05d}",
        user=user,
        first_name=data["firstName"].strip(), middle_name=data["middleName"].strip(), last_name=data["lastName"].strip(),
        gender=data["gender"], dob=data["dob"], phone=data["phone"], email=data["email"],
        address=data["address"].strip(), state=data["state"], lga=data["lga"].strip(),
        qualification=data["qualification"], institution=data["institution"].strip(), grad_year=data["gradYear"],
        waec_status=data["waecStatus"], waec_year=data["waecYear"], num_as=data["numAs"] or 0,
        waec_file=data.get("resultFile") or "",
        programme=programme, cohort=cohort, schedule=data["schedule"],
        fee=q.fee, discount_type=q.discount_type, discount_pct=q.discount_pct,
        discount_amount=q.discount_amount, amount_payable=q.amount_payable,
    )
    ApplicationEvent.objects.create(application=app, text="Application submitted online", actor=user)

    if award_type:
        if award_type == AwardRequest.Type.EXCELLENCE:
            evidence = f"WAEC {app.waec_year} — {app.num_as} A's (declared{', result uploaded' if app.waec_file else ''})"
            requested = settings.excellence_pct
        else:
            evidence = "Intake exam / interview to be scheduled"
            requested = settings.scholarship_max_pct
        AwardRequest.objects.create(application=app, type=award_type, requested_pct=requested, evidence=evidence)
        ApplicationEvent.objects.create(application=app, text=f"{AwardRequest.Type(award_type).label} review requested", actor=user)

    notify(user, "Application received",
           f"Your application {app.number} for {programme.name} has been received. Complete your payment to secure your seat.",
           Notification.Type.APPLICATION)
    if settings.staff_application_alerts:
        notify_staff("New application", f"{app.full_name} applied for {programme.name}.", Notification.Type.APPLICATION)
    return app


def _naira(amount):
    return f"\u20a6{amount:,}"


def mark_paid(app: Application, payment) -> Application:
    """
    A verified successful payment for this application. Activates the student:
    Student record (one per person) + Enrollment + student portal role.
    Must be called inside the transaction that marked the payment SUCCESS.
    """
    from apps.academics.models import Enrollment, Student
    from apps.comms.models import Notification

    app = Application.objects.select_related("user", "programme", "cohort").get(pk=app.pk)
    settings = SiteSettings.load()

    if app.payment_status == Application.PaymentStatus.PAID:
        # Two checkouts both completed (e.g. two tabs). Keep the money on record and flag it.
        ApplicationEvent.objects.create(application=app, text=f"Duplicate payment {payment.reference} ({_naira(payment.amount)}) received — refund required")
        notify_staff("Duplicate payment — refund needed",
                     f"{app.full_name} paid twice for {app.number}. Refund {payment.reference} ({_naira(payment.amount)}).",
                     Notification.Type.PAYMENT)
        return app

    user = app.user
    student = Student.objects.filter(user=user).first()
    if student is None:
        student = Student.objects.create(
            user=user, student_no=f"TSCE/{today().year}/{Sequence.next('student'):05d}",
            first_name=app.first_name, middle_name=app.middle_name, last_name=app.last_name, gender=app.gender,
            dob=app.dob, phone=app.phone, address=app.address, state=app.state, lga=app.lga,
            qualification=app.qualification, institution=app.institution,
        )
    if user.role == User.Role.APPLICANT:
        user.role = User.Role.STUDENT
        user.save(update_fields=["role"])

    events = [ApplicationEvent(application=app, ok=True,
                               text=f"Payment of {_naira(payment.amount)} confirmed via Zainpay ({payment.reference})")]
    enrolled_now = app.status == Application.Status.ACCEPTED
    if enrolled_now:
        app.status = Application.Status.ENROLLED
        events.append(ApplicationEvent(application=app, ok=True, text=f"Enrolled as {student.student_no}"))

    app.payment_status = Application.PaymentStatus.PAID
    app.paid_at = payment.verified_at
    app.save(update_fields=["status", "payment_status", "paid_at", "updated_at"])

    Enrollment.objects.create(
        student=student, application=app, programme=app.programme, cohort=app.cohort, schedule=app.schedule,
        start_date=app.cohort.start_date, end_date=app.programme.end_date_from(app.cohort.start_date),
        status=Enrollment.Status.ACTIVE if enrolled_now else Enrollment.Status.ADMISSION_PENDING,
        amount_paid=payment.amount,
    )
    events.append(ApplicationEvent(application=app, ok=True, text=f"Student portal account activated ({student.student_no})"))
    ApplicationEvent.objects.bulk_create(events)

    notify(user, "Payment successful", f"Your payment of {_naira(payment.amount)} was successful. Ref: {payment.reference}",
           Notification.Type.PAYMENT)
    notify(user, "Welcome to TSCE",
           f"Your student number is {student.student_no}. Classes for the {app.cohort.name} begin on "
           f"{app.cohort.start_date.day} {app.cohort.start_date:%B %Y}.", Notification.Type.ANNOUNCEMENT)
    if settings.staff_payment_alerts:
        notify_staff("Payment received", f"{app.full_name} paid {_naira(payment.amount)} for {app.programme.name}.",
                     Notification.Type.PAYMENT)
    return app


def mark_payment_failed(app: Application, payment) -> None:
    if app.payment_status in (Application.PaymentStatus.PAID, Application.PaymentStatus.REFUNDED):
        return
    Application.objects.filter(pk=app.pk).update(payment_status=Application.PaymentStatus.FAILED)
    ApplicationEvent.objects.create(application=app, text=f"Payment attempt failed ({payment.reference})")


def requote_for_payment(app: Application, settings: SiteSettings) -> Application:
    """
    The early-bird discount depends on the PAYMENT date: an application made
    before the deadline but paid after it pays the full fee. Approved awards
    (excellence/scholarship) are not affected.
    """
    from .models import DiscountType

    if app.discount_type == DiscountType.EARLY_BIRD:
        q = quote(app.programme, app.cohort, settings)
        if q.discount_type != DiscountType.EARLY_BIRD:
            app.discount_type, app.discount_pct = q.discount_type, q.discount_pct
            app.discount_amount, app.amount_payable = q.discount_amount, q.amount_payable
            app.save(update_fields=["discount_type", "discount_pct", "discount_amount", "amount_payable", "updated_at"])
            ApplicationEvent.objects.create(
                application=app, text=f"Early-bird period ended before payment — amount payable is now {_naira(app.amount_payable)}")
    return app
