"""
Seeds the real school data from the TSCE flyer: institution settings, the
October 2026 cohort and the 11 programmes with their modules.

    python manage.py seed_school            # create what's missing; never overwrite
    python manage.py seed_school --update   # also reset programme content to the flyer

No people, applications or payments are created — production starts empty.
"""
import json
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import SiteSettings
from apps.programmes.models import Cohort, Module, Programme

CATALOGUE = Path(__file__).resolve().parents[2] / "data" / "catalogue.json"


class Command(BaseCommand):
    help = "Seed TSCE institution settings, the current cohort and the programme catalogue (from the flyer)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--update", action="store_true",
            help="Overwrite existing programmes (content, fee, duration, modules) with the flyer values.",
        )

    @transaction.atomic
    def handle(self, *args, update=False, **options):
        data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
        flyer = data["flyer"]

        cohort, created = Cohort.objects.get_or_create(
            name="October 2026 Cohort",
            defaults={
                "start_date": date.fromisoformat(flyer["startDate"]),
                "enrolment_opens": date.fromisoformat(flyer["enrolmentOpens"]),
                "enrolment_closes": date.fromisoformat(flyer["enrolmentCloses"]),
                "early_bird_deadline": date.fromisoformat(flyer["earlyBirdDeadline"]),
            },
        )
        self.report("Cohort", cohort, created)

        settings, created = SiteSettings.objects.get_or_create(
            pk=1,
            defaults={
                "institution_name": flyer["name"],
                "short_name": flyer["short"],
                "address": flyer["address"],
                "city": flyer["city"],
                "phones": flyer["phones"],
                "email": flyer["email"],
                "website": flyer["website"],
                "current_cohort": cohort,
                "early_bird_pct": flyer["discounts"]["earlybird"],
                "excellence_pct": flyer["discounts"]["excellence"],
                "scholarship_max_pct": flyer["discounts"]["scholarshipMax"],
            },
        )
        self.report("Site settings", settings, created)

        for p in data["programmes"]:
            fields = {
                "code": p["code"], "name": p["name"], "track": p["track"], "category": p["category"],
                "weeks": p["weeks"], "fee": p["fee"], "capacity": p["capacity"],
                "icon": p["icon"], "color": p["color"], "color_bg": p["colorBg"],
                "overview": p["overview"], "outcomes": p["outcomes"], "audience": p["audience"],
                "careers": p["careers"], "requirements": p["requirements"], "schedules": p["schedules"],
            }
            programme = Programme.objects.filter(slug=p["id"]).first()
            if programme is None:
                programme = Programme.objects.create(slug=p["id"], **fields)
                self.sync_modules(programme, p["modules"])
                self.report("Programme", programme, True)
            elif update:
                for k, v in fields.items():
                    setattr(programme, k, v)
                programme.save()
                self.sync_modules(programme, p["modules"])
                self.stdout.write(f"  updated  Programme: {programme}")
            else:
                self.stdout.write(f"  exists   Programme: {programme}")

        self.stdout.write(self.style.SUCCESS(
            f"Done: {Programme.objects.count()} programmes, {Module.objects.count()} modules, "
            f"current cohort = {SiteSettings.load().current_cohort}."
        ))

    def sync_modules(self, programme, titles):
        """Renames modules in place by position (keeps results attached); adds/removes the tail."""
        existing = {m.order: m for m in programme.modules.all()}
        for order, title in enumerate(titles, start=1):
            module = existing.pop(order, None)
            if module is None:
                Module.objects.create(programme=programme, order=order, title=title)
            elif module.title != title:
                module.title = title
                module.save(update_fields=["title"])
        for module in existing.values():
            if module.results.exists():
                self.stderr.write(f"  kept module '{module}' — it has results recorded")
            else:
                module.delete()

    def report(self, label, obj, created):
        self.stdout.write(f"  {'created' if created else 'exists '}  {label}: {obj}")
