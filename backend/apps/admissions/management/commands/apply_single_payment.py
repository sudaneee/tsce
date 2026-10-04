"""
One-off switch to the single-payment flow (4 Oct 2026). Applications still waiting
for the old separate application fee are admitted now (or sent to award
verification) and told by email/notification that they can pay the programme fee.
Applicants who already paid the ₦5,000 keep it as a credit automatically.

    python manage.py apply_single_payment            # do it
    python manage.py apply_single_payment --dry-run  # just list who would change

Safe to re-run: only "Pending" applications are touched.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.admissions.models import Application, AwardRequest
from apps.admissions.services import admit, await_verification


class Command(BaseCommand):
    help = "Admit applications that were waiting for the (now removed) separate application fee."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, dry_run=False, **options):
        pending = Application.objects.filter(status=Application.Status.PENDING).select_related("user", "programme", "cohort")
        if not pending:
            self.stdout.write("Nothing to do — no applications are waiting for the old application fee.")
            return
        for app in pending:
            award = getattr(app, "award_request", None)
            to_verify = award is not None and award.status == AwardRequest.Status.PENDING
            action = "→ Awaiting Verification" if to_verify else "→ Admitted"
            self.stdout.write(f"{app.number}  {app.full_name}  ({app.programme.name})  {action}")
            if dry_run:
                continue
            with transaction.atomic():
                app = Application.objects.select_related("user", "programme", "cohort").get(pk=app.pk)
                if app.status != Application.Status.PENDING:
                    continue
                if to_verify:
                    await_verification(app)
                else:
                    admit(app)
                    self.stdout.write(f"   programme fee due: ₦{Application.objects.get(pk=app.pk).amount_payable:,}")
        self.stdout.write(self.style.SUCCESS("Dry run — nothing changed." if dry_run else "Done."))
