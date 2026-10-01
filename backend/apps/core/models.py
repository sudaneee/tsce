from django.db import models, transaction
from django.db.models import F


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Sequence(models.Model):
    """
    Named counters behind the human-readable numbers (TSCE/APP/2026/00001,
    TSCE-ZP-20261001-000001, …). Incremented inside a write transaction, so two
    concurrent requests can never be handed the same number.
    """

    name = models.CharField(max_length=40, primary_key=True)
    value = models.PositiveBigIntegerField(default=0)

    def __str__(self):
        return f"{self.name} = {self.value}"

    @classmethod
    def next(cls, name: str) -> int:
        with transaction.atomic():
            # The UPDATE takes SQLite's write lock (IMMEDIATE mode), so the
            # read below sees our own increment and nobody else's.
            if not cls.objects.filter(name=name).update(value=F("value") + 1):
                cls.objects.create(name=name, value=1)
            return cls.objects.get(name=name).value


class SiteSettings(models.Model):
    """Singleton (pk=1) for the settings editable from Staff → Settings."""

    # Institution — shown on receipts, certificates and the website
    institution_name = models.CharField(max_length=200)
    short_name = models.CharField(max_length=20, default="TSCE")
    address = models.CharField(max_length=300)
    city = models.CharField(max_length=120, blank=True)
    phones = models.JSONField(default=list, blank=True)
    email = models.EmailField(blank=True)
    website = models.CharField(max_length=120, blank=True)
    # Signatory printed on certificates
    director_name = models.CharField(max_length=120, blank=True)
    director_title = models.CharField(max_length=120, default="Director, TSCE")

    # Admissions
    current_cohort = models.ForeignKey(
        "programmes.Cohort", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    accepting_applications = models.BooleanField(default=True)
    early_bird_pct = models.PositiveSmallIntegerField(default=15)
    excellence_pct = models.PositiveSmallIntegerField(default=50)
    scholarship_max_pct = models.PositiveSmallIntegerField(default=40)
    excellence_min_waec_year = models.PositiveSmallIntegerField(default=2020)
    excellence_min_as = models.PositiveSmallIntegerField(default=5)

    # Payments (gateway keys and environment live in .env, never here)
    payment_ref_prefix = models.CharField(max_length=20, default="TSCE-ZP")
    allow_card = models.BooleanField(default=True)
    allow_transfer = models.BooleanField(default=True)

    # Notifications
    email_notifications = models.BooleanField(default=True)
    staff_payment_alerts = models.BooleanField(default=True)
    staff_application_alerts = models.BooleanField(default=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "site settings"
        verbose_name_plural = "site settings"

    def __str__(self):
        return "Site settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Site settings cannot be deleted.")

    @classmethod
    def load(cls) -> "SiteSettings":
        obj = cls.objects.select_related("current_cohort").filter(pk=1).first()
        if obj is None:
            raise cls.DoesNotExist("Site settings missing — run: python manage.py seed_school")
        return obj
