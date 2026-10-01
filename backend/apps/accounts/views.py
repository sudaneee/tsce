import secrets
import string

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import services
from .models import User
from .permissions import IsAdmin
from .serializers import ChangePasswordSerializer, LoginSerializer, RegisterSerializer, session_payload


class LoginFailed(APIException):
    # 400, not 401: a wrong password is not an expired session.
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "invalid_credentials"


# DRF skips CSRF for anonymous requests; enforce it here to block login CSRF.
@method_decorator(csrf_protect, name="dispatch")
@method_decorator(sensitive_post_parameters("password"), name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        email, password = data.validated_data["email"], data.validated_data["password"]

        user = authenticate(request, email=email, password=password)
        if user is None:
            # authenticate() returns None for disabled accounts too; tell them apart
            # only when the password is right, so we never reveal which emails exist.
            existing = User.objects.filter(email__iexact=email.strip()).first()
            if existing and not existing.is_active and existing.check_password(password):
                raise LoginFailed("This account has been disabled. Contact the TSCE admin office.", code="account_disabled")
            raise LoginFailed("Incorrect email or password. Please check your details and try again.")

        if user.needs_email_verification:
            services.send_verification_email(user)
            raise LoginFailed("Please verify your email address first. We've sent a new verification link to "
                              f"{user.email}.", code="email_unverified")

        login(request, user)
        # "Keep me signed in" off → session ends when the browser closes.
        request.session.set_expiry(settings.SESSION_COOKIE_AGE if data.validated_data["remember"] else 0)
        return Response({"user": session_payload(user)})


@method_decorator(csrf_protect, name="dispatch")
@method_decorator(sensitive_post_parameters("password"), name="dispatch")
class RegisterView(APIView):
    """
    Create a Student (self) or Parent account. Always answers the same way —
    "check your email" — so nobody can find out which emails are registered.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    def post(self, request):
        data = RegisterSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        d = data.validated_data
        services.register(d["accountType"], d["fullName"].strip(), d["email"], d["phone"], d["password"])
        return Response({"ok": True, "email": d["email"]}, status=status.HTTP_201_CREATED)


@method_decorator(csrf_protect, name="dispatch")
class VerifyEmailView(APIView):
    """POST {token} from the emailed link → verified and signed in (the first time only)."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "verify_email"

    def post(self, request):
        try:
            user, newly = services.verify_email(str(request.data.get("token") or ""))
        except services.InvalidToken as exc:
            raise LoginFailed(str(exc), code="invalid_token")
        if not newly:
            # An old link must not work as a password: already-verified accounts sign in normally.
            return Response({"user": None, "alreadyVerified": True})
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response({"user": session_payload(user), "alreadyVerified": False})


@method_decorator(csrf_protect, name="dispatch")
class ResendVerificationView(APIView):
    """POST {email} → a fresh link if that account still needs one. Same answer either way."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "verify_email"

    def post(self, request):
        email = str(request.data.get("email") or "").strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first() if email else None
        if user and user.needs_email_verification:
            services.send_verification_email(user)
        return Response({"ok": True})


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """The current user, or {"user": null} for visitors (not a 401 — public pages call this)."""

    permission_classes = [AllowAny]

    def get(self, request):
        user = request.user
        return Response({"user": session_payload(user) if user.is_authenticated else None})


@method_decorator(sensitive_post_parameters("currentPassword", "newPassword"), name="dispatch")
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = ChangePasswordSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        user = request.user
        user.set_password(data.validated_data["newPassword"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        update_session_auth_hash(request, user)  # stay signed in on this device
        return Response({"user": session_payload(user)})


def temporary_password(length=10):
    # No look-alike characters (0/O, 1/l/I) — it's read out or typed from a screen.
    alphabet = "".join(c for c in string.ascii_letters + string.digits if c not in "0O1lI")
    return "".join(secrets.choice(alphabet) for _ in range(length))


class AdminResetPasswordView(APIView):
    """
    Until TSCE has an email account, admins reset forgotten passwords here and
    pass the temporary password to the user, who must change it at next login.
    """

    permission_classes = [IsAdmin]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        if user.role == User.Role.ADMIN and not request.user.is_superuser and user != request.user:
            raise PermissionDenied("Only a superuser can reset another administrator's password.")
        password = temporary_password()
        user.set_password(password)
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password"])
        if user == request.user:
            update_session_auth_hash(request, user)
        return Response({"email": user.email, "temporaryPassword": password})
