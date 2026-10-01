from datetime import timedelta

from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel


class Programme(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "Active"
        INACTIVE = "Inactive"

    # The slug is the public id used by the frontend (e.g. "fullstack").
    slug = models.SlugField(max_length=60, unique=True)
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    track = models.CharField(max_length=60, blank=True)
    category = models.CharField(max_length=100, blank=True)
    weeks = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    fee = models.PositiveIntegerField(help_text="Naira")
    capacity = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    instructor = models.ForeignKey(
        "accounts.StaffProfile", null=True, blank=True, on_delete=models.SET_NULL, related_name="programmes"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True)

    # Presentation
    icon = models.CharField(max_length=40, default="fa-laptop-code")
    color = models.CharField(max_length=9, default="#1846D6")
    color_bg = models.CharField(max_length=9, default="#EEF3FF")
    overview = models.TextField(blank=True)
    outcomes = models.JSONField(default=list, blank=True)
    audience = models.JSONField(default=list, blank=True)
    careers = models.JSONField(default=list, blank=True)
    requirements = models.JSONField(default=list, blank=True)
    schedules = models.JSONField(default=list, blank=True, help_text="Class schedule options offered to applicants")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def end_date_from(self, start):
        """Programmes end on the Friday of their last week."""
        return start + timedelta(days=self.weeks * 7 - 3)


class Module(models.Model):
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name="modules")
    order = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=150)

    class Meta:
        ordering = ["programme", "order"]
        constraints = [models.UniqueConstraint(fields=["programme", "order"], name="unique_module_order")]

    def __str__(self):
        return f"{self.programme.code} · {self.order}. {self.title}"


class Cohort(TimeStampedModel):
    """An intake, e.g. "October 2026 Cohort", with its admissions calendar."""

    name = models.CharField(max_length=80, unique=True)
    start_date = models.DateField()
    enrolment_opens = models.DateField(null=True, blank=True)
    enrolment_closes = models.DateField(null=True, blank=True)
    early_bird_deadline = models.DateField(
        null=True, blank=True, help_text="Early-bird discount applies to payments made before this date."
    )

    class Meta:
        ordering = ["-start_date"]

    def __str__(self):
        return self.name
