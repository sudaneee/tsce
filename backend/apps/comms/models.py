from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Notification(models.Model):
    """
    An in-app notification for one user (the bell icon). Staff-wide alerts are
    fanned out to each active staff user so everyone has their own read state.
    """

    class Type(models.TextChoices):
        APPLICATION = "application"
        PAYMENT = "payment"
        SCHOLARSHIP = "scholarship"
        RESULT = "result"
        CERTIFICATE = "certificate"
        ANNOUNCEMENT = "announcement"
        SUPPORT = "support"

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=150)
    body = models.CharField(max_length=500)
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.ANNOUNCEMENT)
    link = models.CharField(max_length=200, blank=True)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "read"])]

    def __str__(self):
        return f"{self.recipient.email}: {self.title}"


class Announcement(TimeStampedModel):
    class Audience(models.TextChoices):
        PUBLIC = "Public"       # website news + everyone
        STUDENTS = "Students"
        STAFF = "Staff"

    class Status(models.TextChoices):
        DRAFT = "Draft"
        PUBLISHED = "Published"

    title = models.CharField(max_length=150)
    body = models.TextField()
    audience = models.CharField(max_length=10, choices=Audience.choices, default=Audience.PUBLIC, db_index=True)
    tag = models.CharField(max_length=40, blank=True)
    pinned = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    author_label = models.CharField(max_length=80, blank=True, help_text='Shown as the sender, e.g. "Admissions Office"')
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-pinned", "-published_at", "-created_at"]

    def __str__(self):
        return self.title


class SupportTicket(TimeStampedModel):
    class Category(models.TextChoices):
        ACADEMIC = "Academic"
        LEARNING = "Learning"
        PAYMENTS = "Payments"
        CERTIFICATES = "Certificates"
        ICT = "ICT / Portal"
        OTHER = "Other"

    class Priority(models.TextChoices):
        NORMAL = "Normal"
        HIGH = "High"

    class Status(models.TextChoices):
        OPEN = "Open"
        RESOLVED = "Resolved"

    number = models.CharField(max_length=20, unique=True)  # TKT-1001
    student = models.ForeignKey("academics.Student", on_delete=models.CASCADE, related_name="tickets")
    category = models.CharField(max_length=20, choices=Category.choices)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    subject = models.CharField(max_length=150)
    message = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN, db_index=True)
    reply = models.TextField(blank=True)
    replied_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    replied_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.number} — {self.subject}"


class Enquiry(TimeStampedModel):
    """A message from the public contact form."""

    class Status(models.TextChoices):
        NEW = "New"
        HANDLED = "Handled"

    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    programme = models.CharField(max_length=150, blank=True)
    subject = models.CharField(max_length=150, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "enquiries"

    def __str__(self):
        return f"{self.name}: {self.subject or self.programme or 'General enquiry'}"
