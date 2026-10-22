# Fills a fresh e2e database (see e2e/run.sh). User ids: director=1, rabi=2, amina=3.
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import User

call_command("seed_school")
User.objects.create_superuser("director@tsce.edu.ng", "Director-Pass-2026", full_name="Test Director")
User.objects.create_user("rabi@tsce.edu.ng", "Staff-Pass-2026", full_name="Rabi Isa", role="staff")
amina = User.objects.create_user("amina@example.com", "Student-Pass-2026", full_name="Amina Yusuf", role="student",
                                 email_verified_at=timezone.now())
# Amina's application, so an admin can reset her password from it
from datetime import date  # noqa: E402

from apps.admissions.models import Application  # noqa: E402
from apps.core.models import SiteSettings  # noqa: E402
from apps.programmes.models import Programme  # noqa: E402

prog = Programme.objects.get(slug="network")
Application.objects.create(number="TSCE/APP/2026/00001", user=amina, first_name="Amina", last_name="Yusuf", gender="Female",
                           dob=date(2003, 3, 3), phone="0803 123 4567", email=amina.email, address="Zaria", state="Kaduna",
                           lga="Zaria", qualification="SSCE", institution="Barewa", waec_status="Not Applicable", programme=prog,
                           cohort=SiteSettings.load().current_cohort, schedule=prog.schedules[0], fee=prog.fee,
                           amount_payable=prog.fee + 5000, status="Admitted")
print("e2e setup done")
