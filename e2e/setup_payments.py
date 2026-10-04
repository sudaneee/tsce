# Fills a fresh e2e database (see e2e/run.sh): two verified self-applicants admitted on applying, nothing paid yet.
from datetime import date

from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import User
from apps.admissions.models import Application, ApplicationEvent
from apps.core.models import SiteSettings
from apps.programmes.models import Programme

call_command("seed_school")
User.objects.create_user("rabi@tsce.edu.ng", "Staff-Pass-2026", full_name="Rabi Isa", role="staff")
cohort = SiteSettings.load().current_cohort
for n, (first, last, email, slug) in enumerate([("Aisha", "Garba", "aisha@example.com", "fullstack"),
                                                ("Musa", "Bello", "musa@example.com", "network")], start=1):
    user = User.objects.create_user(email, "Applicant-Pass-2026", full_name=f"{first} {last}", role="applicant",
                                    phone="0803 123 4567", email_verified_at=timezone.now())
    prog = Programme.objects.get(slug=slug)
    app = Application.objects.create(
        number=f"TSCE/APP/2026/{n:05d}", user=user, first_name=first, last_name=last, gender="Female",
        dob=date(2002, 5, 14), phone="0803 123 4567", email=email, address="Samaru, Zaria", state="Kaduna", lga="Zaria",
        qualification="OND", institution="NBP", grad_year=2023, waec_status="Not Applicable", programme=prog,
        cohort=cohort, schedule=prog.schedules[0], application_fee=5000, fee=prog.fee, amount_payable=prog.fee + 5000,
        status="Admitted")
    ApplicationEvent.objects.create(application=app, text="Application submitted online")
print("e2e setup done")
