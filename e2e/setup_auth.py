from django.core.management import call_command

from apps.accounts.models import User

call_command("seed_school")
User.objects.create_superuser("director@tsce.edu.ng", "Director-Pass-2026", full_name="Test Director")
User.objects.create_user("rabi@tsce.edu.ng", "Staff-Pass-2026", full_name="Rabi Isa", role="staff")
User.objects.create_user("amina@example.com", "Student-Pass-2026", full_name="Amina Yusuf", role="student")
print("e2e setup done")
