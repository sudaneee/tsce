# Fills a fresh e2e database (see e2e/run.sh) with one application in each interesting state.
from datetime import date, timedelta

from django.core.management import call_command
from django.utils import timezone

from apps.academics.models import Enrollment, Student
from apps.accounts.models import User
from apps.admissions.models import Application, ApplicationEvent, AwardRequest
from apps.comms.models import Notification
from apps.core.models import SiteSettings
from apps.payments.models import Payment
from apps.programmes.models import Programme

call_command("seed_school")
now = timezone.now()
User.objects.create_superuser("director@tsce.edu.ng", "Director-Pass-2026", full_name="Test Director")
rabi = User.objects.create_user("rabi@tsce.edu.ng", "Staff-Pass-2026", full_name="Rabi Isa", role="staff", email_verified_at=now)
cohort = SiteSettings.load().current_cohort


def account(email, name, role):
    return User.objects.create_user(email, "Applicant-Pass-2026", full_name=name, role=role, phone="0803 123 4567",
                                    email_verified_at=now)


def app(n, user, first, last, slug, status, **extra):
    prog = Programme.objects.get(slug=slug)
    a = Application.objects.create(
        number=f"TSCE/APP/2026/{n:05d}", user=user, first_name=first, last_name=last, gender="Female",
        dob=date(2005, 3, 1), phone="0803 123 4567", email="", address="Kongo, Zaria", state="Kaduna", lga="Zaria",
        qualification="SSCE", institution="Barewa College", waec_status="Available", waec_year=2024, num_as=7,
        programme=prog, cohort=cohort, schedule=prog.schedules[0], application_fee=5000, fee=prog.fee,
        amount_payable=prog.fee, status=status, **extra)
    ApplicationEvent.objects.create(application=a, text="Application submitted online")
    return a


def pay(a, ref, purpose, amount, minutes):
    return Payment.objects.create(reference=ref, purpose=purpose, application=a, user=a.user, name=a.full_name,
                                  email=a.user.email, description=purpose, amount=amount, gateway="zainpay",
                                  status="SUCCESS", verified_at=now + timedelta(minutes=minutes))


# 1. Pending (application fee not paid)
app(1, account("aisha@example.com", "Aisha Garba", "applicant"), "Aisha", "Garba", "fullstack", "Pending")
# 2. Parent's child awaiting Excellence Award verification
parent = account("musa@example.com", "Musa Bello", "parent")
umar = app(2, parent, "Umar", "Bello", "network", "Awaiting Verification", application_fee_paid_at=now)
AwardRequest.objects.create(application=umar, type="excellence", requested_pct=50, evidence="WAEC 2024 — 7 A's (declared)")
pay(umar, "TSCE-ZP-20261001-000010", "application_fee", 5000, 0)
# 3. Enrolled, but the application fee was paid twice (duplicate to refund)
zainab_user = account("zainab@example.com", "Zainab Sani", "student")
zainab = app(3, zainab_user, "Zainab", "Sani", "data-ai", "Enrolled", application_fee_paid_at=now, payment_status="Paid", paid_at=now)
pay(zainab, "TSCE-ZP-20261001-000011", "application_fee", 5000, 0)
pay(zainab, "TSCE-ZP-20261001-000012", "application_fee", 5000, 3)
pay(zainab, "TSCE-ZP-20261001-000013", "programme_fee", 45000, 10)
student = Student.objects.create(user=zainab_user, student_no="TSCE/2026/00001", first_name="Zainab", last_name="Sani",
                                 gender="Female", phone="0803 123 4567")
Enrollment.objects.create(student=student, application=zainab, programme=zainab.programme, cohort=cohort,
                          schedule=zainab.schedule, start_date=cohort.start_date,
                          end_date=zainab.programme.end_date_from(cohort.start_date), amount_paid=45000)
Notification.objects.create(recipient=rabi, title="Excellence Award to verify", body="Umar Bello will bring a result.", type="scholarship")
print("e2e setup done")
