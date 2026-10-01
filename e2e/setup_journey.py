# Fills a fresh e2e database (see e2e/run.sh): school data + one admissions officer.
from django.core.management import call_command

from apps.accounts.models import User

call_command("seed_school")
User.objects.create_user("rabi@tsce.edu.ng", "Staff-Pass-2026", full_name="Rabi Isa", role="staff")
print("e2e setup done")
