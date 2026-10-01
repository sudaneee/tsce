"""Account registration and email verification."""
from django.conf import settings
from django.core import signing
from django.db import transaction
from django.utils import timezone

from apps.core.emails import send_email, site_link
from apps.core.exceptions import ServiceError

from .models import User

VERIFY_SALT = "tsce.accounts.verify-email"


def verification_token(user: User) -> str:
    # Bound to the email too, so a link stops working if the address changes.
    return signing.dumps({"u": user.pk, "e": user.email}, salt=VERIFY_SALT)


def send_verification_email(user: User) -> bool:
    link = site_link(f"pages/verify-email.html?token={verification_token(user)}")
    hours = settings.EMAIL_VERIFICATION_MAX_AGE // 3600
    return send_email(
        "Verify your email — TSCE admissions portal",
        f"Dear {user.full_name},\n\nWelcome to the TSCE admissions portal. Please confirm your email address "
        f"by opening this link (valid for {hours} hours):\n\n{link}\n\n"
        "If you didn't create an account, you can ignore this email.",
        user.email,
    )


def send_already_registered_email(user: User) -> bool:
    return send_email(
        "Your TSCE account",
        f"Dear {user.full_name},\n\nSomeone (hopefully you) tried to register with this email address, but an "
        f"account already exists. Sign in here: {site_link('pages/login.html')}\n\n"
        "Forgot your password? Contact the TSCE admin office to reset it.",
        user.email,
    )


@transaction.atomic
def register(account_type: str, full_name: str, email: str, phone: str, password: str) -> User | None:
    """
    Creates an unverified account and emails a verification link. If the email
    is already registered, nothing is created and the owner is told by email —
    the caller answers identically either way, so emails can't be probed.
    """
    existing = User.objects.filter(email__iexact=email).first()
    if existing:
        if existing.needs_email_verification:
            send_verification_email(existing)
        else:
            send_already_registered_email(existing)
        return None
    role = User.Role.PARENT if account_type == "parent" else User.Role.APPLICANT
    user = User.objects.create_user(email, password, full_name=full_name, phone=phone, role=role)
    transaction.on_commit(lambda: send_verification_email(user))
    return user


class InvalidToken(Exception):
    pass


def verify_email(token: str) -> tuple[User, bool]:
    """Returns (user, newly_verified). Raises InvalidToken for bad, expired or stale links."""
    try:
        data = signing.loads(token, salt=VERIFY_SALT, max_age=settings.EMAIL_VERIFICATION_MAX_AGE)
    except signing.SignatureExpired:
        raise InvalidToken("This verification link has expired. Request a new one below.")
    except signing.BadSignature:
        raise InvalidToken("This verification link isn't valid. Request a new one below.")
    user = User.objects.filter(pk=data.get("u"), email=data.get("e"), is_active=True).first()
    if user is None:
        raise InvalidToken("This verification link isn't valid. Request a new one below.")
    if user.email_verified:
        return user, False
    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    return user, True


# ---------------------------------------------------------------------------
# Staff accounts (admin only). Instructors may have no portal login at all.
# ---------------------------------------------------------------------------
ACCESS_NONE, ACCESS_STAFF, ACCESS_ADMIN = "none", "staff", "admin"


def staff_access(profile) -> str:
    user = profile.user
    if user is None or not user.is_active:
        return ACCESS_NONE
    return ACCESS_ADMIN if user.role == User.Role.ADMIN else ACCESS_STAFF


def ensure_staff_profiles():
    """Portal staff created outside this screen (e.g. createsuperuser) get a profile row."""
    from apps.core.models import Sequence

    from .models import StaffProfile

    for user in User.objects.filter(role__in=[User.Role.STAFF, User.Role.ADMIN], staff_profile__isnull=True):
        StaffProfile.objects.create(
            user=user, staff_no=f"STF-{Sequence.next('staff'):03d}", full_name=user.full_name,
            title="Administrator" if user.role == User.Role.ADMIN else "Staff",
            department=StaffProfile.Department.MANAGEMENT, email=user.email, phone=user.phone,
        )


def _grant_login(profile, access: str):
    """Creates or re-activates the portal login. Returns a temporary password when one was set."""
    from .views import temporary_password

    role = User.Role.ADMIN if access == ACCESS_ADMIN else User.Role.STAFF
    user = profile.user
    if user is None:
        if not profile.email:
            raise ServiceError("An email address is needed for portal access.", "invalid", field="email")
        if User.objects.filter(email__iexact=profile.email).exists():
            raise ServiceError("Another account already uses this email.", "invalid", field="email")
        password = temporary_password()
        user = User.objects.create_user(profile.email, password, full_name=profile.full_name, phone=profile.phone,
                                        role=role, email_verified_at=timezone.now(), must_change_password=True)
        profile.user = user
        profile.save(update_fields=["user"])
        return password
    user.role, user.is_active = role, True
    user.save(update_fields=["role", "is_active"])
    return None


@transaction.atomic
def create_staff(data: dict):
    from apps.core.models import Sequence

    from .models import StaffProfile

    profile = StaffProfile.objects.create(
        staff_no=f"STF-{Sequence.next('staff'):03d}", full_name=data["fullName"], title=data["title"],
        department=data["department"], email=data.get("email", ""), phone=data.get("phone", ""),
        joined_on=timezone.localdate(),
    )
    password = _grant_login(profile, data["access"]) if data["access"] != ACCESS_NONE else None
    return profile, password


@transaction.atomic
def update_staff(profile, data: dict, actor: User):
    """Edits a staff member. Returns a temporary password if a new login was created."""
    from .models import StaffProfile

    is_self = profile.user_id == actor.pk
    if is_self and (data.get("access", staff_access(profile)) != staff_access(profile)
                    or data.get("status", profile.status) != StaffProfile.Status.ACTIVE):
        raise ServiceError("You can't change your own access or deactivate your own account.", "self_change")

    for field, attr in (("fullName", "full_name"), ("title", "title"), ("department", "department"),
                        ("phone", "phone"), ("status", "status"), ("email", "email")):
        if field in data:
            setattr(profile, attr, data[field])
    profile.save()

    password = None
    access = data.get("access", staff_access(profile))
    if profile.status != StaffProfile.Status.ACTIVE or access == ACCESS_NONE:
        if profile.user:
            profile.user.is_active = False
            profile.user.save(update_fields=["is_active"])
    else:
        password = _grant_login(profile, access)
    if profile.user:  # keep the login's name/phone in step with the profile
        profile.user.full_name, profile.user.phone = profile.full_name, profile.phone
        profile.user.save(update_fields=["full_name", "phone"])
    return password
