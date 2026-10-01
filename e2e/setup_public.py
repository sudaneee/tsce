# Fills a fresh e2e database (see e2e/run.sh).
from datetime import date, timedelta

from django.core.management import call_command
from django.utils import timezone

from apps.academics.models import Certificate, Enrollment, Student
from apps.accounts.models import User
from apps.admissions.models import Application
from apps.comms.models import Announcement
from apps.programmes.models import Cohort, Programme

call_command("seed_school")
User.objects.create_user("rabi@tsce.edu.ng", "Staff-Pass-2026", full_name="Rabi Isa", role="staff")
Announcement.objects.create(title="Orientation for new students", body="Orientation holds on Saturday 10 October at the main hall.",
                            audience="Public", status="Published", tag="Event", author_label="Admissions Office",
                            published_at=timezone.now())

# A graduate with an issued certificate (for verify.html)
grad = User.objects.create_user("grad@example.com", "Grad-Pass-2026", full_name="Bello Musa", role="student")
cohort = Cohort.objects.create(name="July 2026 Cohort", start_date=date(2026, 6, 1))
prog = Programme.objects.get(slug="cyber-fund")
app = Application.objects.create(number="TSCE/APP/2026/90001", user=grad, first_name="Bello", last_name="Musa", gender="Male",
                                 dob=date(2000, 1, 1), phone="0803 111 2222", email=grad.email, address="Zaria", state="Kaduna",
                                 lga="Zaria", qualification="B.Sc", institution="ABU", waec_status="Not Applicable",
                                 programme=prog, cohort=cohort, schedule=prog.schedules[0], fee=45000, amount_payable=45000,
                                 status="Enrolled", payment_status="Paid")
st = Student.objects.create(user=grad, student_no="TSCE/2026/90001", first_name="Bello", last_name="Musa", gender="Male", phone=app.phone)
en = Enrollment.objects.create(student=st, application=app, programme=prog, cohort=cohort, schedule=app.schedule,
                               start_date=cohort.start_date, end_date=cohort.start_date + timedelta(days=39), status="Completed", progress=100)
Certificate.objects.create(number="TSCE/CERT/2026/90001", enrollment=en, issued_at=timezone.now())
print("e2e setup done")
