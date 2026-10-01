import math

from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models

from apps.core.models import TimeStampedModel

from .grading import grade_for


class Student(TimeStampedModel):
    """
    A person enrolled at TSCE, created when their programme fee is paid.
    Self-applicants sign in as themselves (user). A parent's child has no login
    of their own (user is empty) and is managed through the guardian's account.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="student")
    guardian = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    student_no = models.CharField("student number", max_length=30, unique=True)  # TSCE/2026/00001
    first_name = models.CharField(max_length=60)
    middle_name = models.CharField(max_length=60, blank=True)
    last_name = models.CharField(max_length=60)
    gender = models.CharField(max_length=10)
    dob = models.DateField("date of birth", null=True, blank=True)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=300, blank=True)
    state = models.CharField(max_length=40, blank=True)
    lga = models.CharField("LGA", max_length=80, blank=True)
    qualification = models.CharField(max_length=40, blank=True)
    institution = models.CharField(max_length=200, blank=True)
    emergency_contact = models.CharField(max_length=200, blank=True)
    prefs = models.JSONField(default=dict, blank=True, help_text="Notification preferences")

    class Meta:
        ordering = ["first_name", "last_name"]

    def __str__(self):
        return f"{self.student_no} — {self.full_name}"

    @property
    def full_name(self):
        return " ".join(p for p in (self.first_name, self.middle_name, self.last_name) if p)

    @property
    def account(self):
        """The login that manages this student: their own, or their parent's."""
        return self.user or self.guardian


class Enrollment(TimeStampedModel):
    """A student's place on one programme in one cohort."""

    class Status(models.TextChoices):
        ACTIVE = "Active"
        COMPLETED = "Completed"
        SUSPENDED = "Suspended"
        WITHDRAWN = "Withdrawn"

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="enrollments")
    application = models.OneToOneField("admissions.Application", on_delete=models.PROTECT, related_name="enrollment")
    programme = models.ForeignKey("programmes.Programme", on_delete=models.PROTECT, related_name="enrollments")
    cohort = models.ForeignKey("programmes.Cohort", on_delete=models.PROTECT, related_name="enrollments")
    schedule = models.CharField(max_length=80)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    # Overall completion, set by staff. Per-module progress is derived from it.
    progress = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(100)])
    amount_paid = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["student", "programme", "cohort"], name="unique_enrollment_per_cohort")
        ]

    def __str__(self):
        return f"{self.student.full_name} · {self.programme.code} · {self.cohort}"

    def module_progress(self, modules=None):
        """Per-module completion derived from overall progress: [(module, pct), …]."""
        modules = list(modules if modules is not None else self.programme.modules.all())
        done = self.progress / 100 * len(modules)
        out = []
        for i, m in enumerate(modules):
            if i + 1 <= math.floor(done):
                pct = 100
            elif i < done:
                pct = round((done - i) * 100)
            else:
                pct = 0
            out.append((m, pct))
        return out


class AttendanceSession(models.Model):
    """One class meeting for a programme's cohort."""

    programme = models.ForeignKey("programmes.Programme", on_delete=models.PROTECT, related_name="sessions")
    cohort = models.ForeignKey("programmes.Cohort", on_delete=models.PROTECT, related_name="sessions")
    date = models.DateField()
    module = models.ForeignKey("programmes.Module", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date"]
        constraints = [models.UniqueConstraint(fields=["programme", "cohort", "date"], name="unique_session_per_day")]

    def __str__(self):
        return f"{self.programme.code} · {self.date}"


class AttendanceRecord(models.Model):
    class Status(models.TextChoices):
        PRESENT = "Present"
        LATE = "Late"
        ABSENT = "Absent"

    session = models.ForeignKey(AttendanceSession, on_delete=models.CASCADE, related_name="records")
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="attendance")
    status = models.CharField(max_length=10, choices=Status.choices)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["session", "enrollment"], name="unique_attendance_mark")]

    def __str__(self):
        return f"{self.enrollment.student.full_name} · {self.session.date} · {self.status}"


class Result(TimeStampedModel):
    """An assessment score for one module."""

    class Type(models.TextChoices):
        PRACTICAL = "Practical Assignment"
        TEST = "Module Test"
        PROJECT = "Project"
        CAPSTONE = "Capstone Project"

    class Status(models.TextChoices):
        DRAFT = "Draft"
        PUBLISHED = "Published"

    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="results")
    module = models.ForeignKey("programmes.Module", on_delete=models.PROTECT, related_name="results")
    type = models.CharField(max_length=30, choices=Type.choices)
    score = models.PositiveSmallIntegerField(validators=[MaxValueValidator(100)])
    grade = models.CharField(max_length=1, editable=False)
    remark = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)
    assessed_on = models.DateField()
    published_at = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["assessed_on"]
        constraints = [models.UniqueConstraint(fields=["enrollment", "module"], name="unique_result_per_module")]

    def __str__(self):
        return f"{self.enrollment.student.full_name} · {self.module.title} · {self.score}"

    def save(self, *args, **kwargs):
        self.grade = grade_for(self.score)
        super().save(*args, **kwargs)


class Certificate(models.Model):
    """Issued when a student completes a programme; verified publicly by number."""

    class Status(models.TextChoices):
        ISSUED = "Issued"
        REVOKED = "Revoked"

    number = models.CharField(max_length=30, unique=True)  # TSCE/CERT/2026/00001
    enrollment = models.OneToOneField(Enrollment, on_delete=models.PROTECT, related_name="certificate")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ISSUED)
    issued_at = models.DateTimeField()
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return self.number
