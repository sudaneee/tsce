"""
Custom user model. It is created in Phase 0 because AUTH_USER_MODEL must be in
place before the first migration — changing it later is very painful.
"""
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def get_by_natural_key(self, email):
        return self.get(email__iexact=email.strip())

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("role", User.Role.ADMIN)
        extra.setdefault("email_verified_at", timezone.now())
        extra["is_staff"] = True
        extra["is_superuser"] = True
        return self._create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        APPLICANT = "applicant", "Applicant"     # applying for themselves, not enrolled yet
        PARENT = "parent", "Parent / Guardian"   # applies for and manages their children
        STUDENT = "student", "Student"           # enrolled self-applicant
        STAFF = "staff", "Staff"
        ADMIN = "admin", "Admin"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.APPLICANT, db_index=True)
    is_active = models.BooleanField(default=True)
    # Access to the Django admin back office (not the same as the staff portal).
    is_staff = models.BooleanField(default=False)
    # Applicants and parents must verify their email before applying or signing in.
    email_verified_at = models.DateTimeField(null=True, blank=True)
    # Set when an admin resets the password; the portal then forces a change.
    must_change_password = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} <{self.email}>"

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    @property
    def email_verified(self):
        return self.email_verified_at is not None

    @property
    def needs_email_verification(self):
        """Only self-registered accounts verify by email; admins create staff accounts."""
        return self.role in (self.Role.APPLICANT, self.Role.PARENT, self.Role.STUDENT) and not self.email_verified

    @property
    def can_apply(self):
        return self.role in (self.Role.APPLICANT, self.Role.PARENT, self.Role.STUDENT)

    @property
    def is_portal_staff(self):
        return self.role in (self.Role.STAFF, self.Role.ADMIN)


class StaffProfile(models.Model):
    """
    A member of TSCE staff. Admissions, finance and management staff have a
    portal login (user); instructors are listed here without one — admin staff
    enter attendance and results on their behalf.
    """

    class Department(models.TextChoices):
        MANAGEMENT = "Management"
        ADMISSIONS = "Admissions"
        FINANCE = "Finance"
        ACADEMICS = "Academics"

    class Status(models.TextChoices):
        ACTIVE = "Active"
        ON_LEAVE = "On Leave"
        INACTIVE = "Inactive"

    user = models.OneToOneField(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="staff_profile")
    staff_no = models.CharField("staff number", max_length=20, unique=True)
    full_name = models.CharField(max_length=150)
    title = models.CharField("job title", max_length=120)
    department = models.CharField(max_length=20, choices=Department.choices)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    joined_on = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["staff_no"]

    def __str__(self):
        return f"{self.full_name} ({self.title})"
