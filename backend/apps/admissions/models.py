import uuid
from pathlib import Path

from django.conf import settings
from django.core.validators import FileExtensionValidator, MaxValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.core.storage import private_storage


def waec_upload_path(instance, filename):
    ext = Path(filename).suffix.lower()
    return f"waec/{timezone.now():%Y/%m}/{uuid.uuid4().hex}{ext}"


class DiscountType(models.TextChoices):
    EARLY_BIRD = "earlybird", "Early Bird Discount"
    EXCELLENCE = "excellence", "Excellence Award"
    SCHOLARSHIP = "scholarship", "Performance Scholarship"


class Application(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "Pending"
        UNDER_REVIEW = "Under Review"
        ACCEPTED = "Accepted"
        ENROLLED = "Enrolled"
        REJECTED = "Rejected"

    class PaymentStatus(models.TextChoices):
        UNPAID = "Unpaid"
        PENDING = "Pending"      # bank transfer started, not yet confirmed
        PAID = "Paid"
        FAILED = "Failed"
        REFUNDED = "Refunded"

    class Gender(models.TextChoices):
        FEMALE = "Female"
        MALE = "Male"

    class WaecStatus(models.TextChoices):
        AVAILABLE = "Available"
        AWAITING = "Awaiting Result"
        NOT_APPLICABLE = "Not Applicable"

    number = models.CharField(max_length=30, unique=True)  # TSCE/APP/2026/00001
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="applications")

    # Personal (a snapshot of what the applicant submitted)
    first_name = models.CharField(max_length=60)
    middle_name = models.CharField(max_length=60, blank=True)
    last_name = models.CharField(max_length=60)
    gender = models.CharField(max_length=10, choices=Gender.choices)
    dob = models.DateField("date of birth")
    phone = models.CharField(max_length=30)
    email = models.EmailField(db_index=True)
    address = models.CharField(max_length=300)
    state = models.CharField(max_length=40)
    lga = models.CharField("LGA", max_length=80)

    # Education
    qualification = models.CharField(max_length=40)
    institution = models.CharField(max_length=200)
    grad_year = models.PositiveSmallIntegerField(null=True, blank=True)
    waec_status = models.CharField(max_length=20, choices=WaecStatus.choices)
    waec_year = models.PositiveSmallIntegerField(null=True, blank=True)
    num_as = models.PositiveSmallIntegerField("number of A's", default=0, validators=[MaxValueValidator(9)])
    waec_file = models.FileField(
        upload_to=waec_upload_path, storage=private_storage, blank=True,
        validators=[FileExtensionValidator(["pdf", "jpg", "jpeg", "png"])],
    )

    # Programme
    programme = models.ForeignKey("programmes.Programme", on_delete=models.PROTECT, related_name="applications")
    cohort = models.ForeignKey("programmes.Cohort", on_delete=models.PROTECT, related_name="applications")
    schedule = models.CharField(max_length=80)

    # Fees (naira) — fixed when the application is created / an award is approved
    fee = models.PositiveIntegerField()
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices, blank=True)
    discount_pct = models.PositiveSmallIntegerField(default=0)
    discount_amount = models.PositiveIntegerField(default=0)
    amount_payable = models.PositiveIntegerField()

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    payment_status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID, db_index=True
    )
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.number} — {self.full_name}"

    @property
    def full_name(self):
        return " ".join(p for p in (self.first_name, self.middle_name, self.last_name) if p)


class ApplicationEvent(models.Model):
    """The activity timeline shown on an application."""

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="events")
    at = models.DateTimeField(default=timezone.now)
    text = models.CharField(max_length=300)
    ok = models.BooleanField(default=False, help_text="Positive milestone (shown in green)")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["at", "id"]

    def __str__(self):
        return self.text


class AwardRequest(TimeStampedModel):
    """An Excellence Award or Performance Scholarship request, reviewed by staff."""

    class Type(models.TextChoices):
        EXCELLENCE = DiscountType.EXCELLENCE
        SCHOLARSHIP = DiscountType.SCHOLARSHIP

    class Status(models.TextChoices):
        PENDING = "Pending"
        APPROVED = "Approved"
        REJECTED = "Rejected"

    application = models.OneToOneField(Application, on_delete=models.CASCADE, related_name="award_request")
    type = models.CharField(max_length=20, choices=Type.choices)
    requested_pct = models.PositiveSmallIntegerField()
    awarded_pct = models.PositiveSmallIntegerField(null=True, blank=True)
    interview_score = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(100)])
    evidence = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    note = models.CharField(max_length=300, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_type_display()} — {self.application.full_name}"
