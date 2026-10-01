from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel


class Payment(TimeStampedModel):
    """
    A money movement through the gateway: a charge (applicant → TSCE) or a
    refund (TSCE → applicant). Amounts are whole naira.
    """

    class Kind(models.TextChoices):
        CHARGE = "charge", "Charge"
        REFUND = "refund", "Refund"

    class Status(models.TextChoices):
        PENDING = "PENDING"
        SUCCESS = "SUCCESS"
        FAILED = "FAILED"
        REFUNDED = "REFUNDED"   # a charge that has been fully refunded

    class Channel(models.TextChoices):
        CARD = "card", "Card"
        TRANSFER = "transfer", "Bank transfer"
        VIRTUAL = "virtual", "Virtual account"
        OTHER = "other", "Other"

    reference = models.CharField(max_length=40, unique=True)  # TSCE-ZP-20261001-000001 (refunds end in -RF)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.CHARGE)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="refunds",
        help_text="For refunds: the charge being refunded",
    )
    application = models.ForeignKey(
        "admissions.Application", null=True, blank=True, on_delete=models.PROTECT, related_name="payments"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="payments")
    name = models.CharField(max_length=150)
    email = models.EmailField()
    description = models.CharField(max_length=200)

    amount = models.PositiveIntegerField(help_text="Naira")
    fee = models.PositiveIntegerField(default=0, help_text="Programme fee before discount")
    discount = models.PositiveIntegerField(default=0)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    channel = models.CharField(max_length=10, choices=Channel.choices, blank=True)
    gateway = models.CharField(max_length=20)  # zainpay | simulator | manual
    gateway_ref = models.CharField(max_length=100, blank=True, db_index=True)
    checkout_url = models.URLField(max_length=500, blank=True)
    gateway_payload = models.JSONField(default=dict, blank=True, help_text="Last verify/webhook response")
    failure_reason = models.CharField(max_length=300, blank=True)

    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Set when staff confirm a payment manually",
    )
    refunded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(kind="charge", parent__isnull=True) | Q(kind="refund", parent__isnull=False),
                name="refund_has_parent_charge",
            )
        ]

    def __str__(self):
        return f"{self.reference} · ₦{self.amount:,} · {self.status}"


class WebhookEvent(models.Model):
    """Every webhook call is stored before processing — for audit and replay."""

    gateway = models.CharField(max_length=20)
    event_type = models.CharField(max_length=60, blank=True)
    reference = models.CharField(max_length=100, blank=True, db_index=True)
    payload = models.JSONField(default=dict)
    headers = models.JSONField(default=dict)
    signature_valid = models.BooleanField(default=False)
    processed = models.BooleanField(default=False)
    error = models.TextField(blank=True)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-received_at"]

    def __str__(self):
        return f"{self.gateway} {self.event_type} {self.reference}"
