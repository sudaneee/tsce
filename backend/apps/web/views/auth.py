"""Sign in, register, verify email, sign out, change password — as server-rendered forms."""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from apps.accounts import services
from apps.accounts.models import User

from ..context import home_for
from ..forms import EmailForm, LoginForm, RegisterForm
from ..throttle import allow
from .common import LOGIN_URL, safe_next

TOO_MANY = "Too many attempts. Please wait a minute and try again."


@sensitive_post_parameters("password")
def login_view(request):
    portal = "staff" if request.GET.get("role") == "staff" else "student"
    form = LoginForm(request.POST or None)
    error = ""
    if request.method == "POST" and form.is_valid():
        if not allow(request, "login"):
            error = TOO_MANY
        else:
            email, password = form.cleaned_data["email"], form.cleaned_data["password"]
            user = authenticate(request, email=email, password=password)
            if user is None:
                existing = User.objects.filter(email__iexact=email.strip()).first()
                if existing and not existing.is_active and existing.check_password(password):
                    error = "This account has been disabled. Contact the TSCE admin office."
                else:
                    error = "Incorrect email or password. Please check your details and try again."
            elif user.needs_email_verification:
                services.send_verification_email(user)
                error = f"Please verify your email address first. We've sent a new verification link to {user.email}."
            else:
                login(request, user)
                request.session.set_expiry(settings.SESSION_COOKIE_AGE if form.cleaned_data["remember"] else 0)
                if user.must_change_password and not user.is_portal_staff:
                    return redirect("/account/password/")
                return redirect(safe_next(request, home_for(user)))
    return render(request, "web/auth/login.html", {
        "form": form, "error": error, "portal": portal, "signed_out": request.GET.get("out") == "1",
        "next": request.GET.get("next", ""),
    })


@sensitive_post_parameters("password", "password2")
def register_view(request):
    form = RegisterForm(request.POST or None)
    error = ""
    if request.method == "POST" and form.is_valid():
        if not allow(request, "register"):
            error = TOO_MANY
        else:
            d = form.cleaned_data
            services.register(d["accountType"], d["fullName"].strip(), d["email"], d["phone"], d["password"])
            # Same answer whether or not the email was already registered.
            return render(request, "web/auth/check_email.html", {"email": d["email"]})
    return render(request, "web/auth/register.html", {"form": form, "error": error})


def verify_email_view(request):
    """The emailed link opens this page; the button confirms (link scanners only ever GET)."""
    token = request.POST.get("token") or request.GET.get("token") or ""
    ctx = {"token": token, "resend": EmailForm()}
    if request.method == "POST":
        if not allow(request, "verify_email"):
            ctx["error"] = TOO_MANY
        else:
            try:
                user, newly = services.verify_email(token)
            except services.InvalidToken as exc:
                ctx["error"] = str(exc)
            else:
                if not newly:
                    messages.info(request, "Your email is already verified — please sign in.")
                    return redirect(LOGIN_URL)
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                messages.success(request, "Email verified — welcome to TSCE! You can apply now.")
                return redirect("/my-applications/")
    elif not token:
        ctx["error"] = "This verification link is incomplete. Request a new one below."
    return render(request, "web/auth/verify_email.html", ctx)


@require_POST
def resend_verification_view(request):
    form = EmailForm(request.POST)
    if form.is_valid() and allow(request, "verify_email"):
        user = User.objects.filter(email__iexact=form.cleaned_data["email"].strip(), is_active=True).first()
        if user and user.needs_email_verification:
            services.send_verification_email(user)
    return render(request, "web/auth/check_email.html", {"email": form.cleaned_data.get("email", "") if form.is_valid() else "",
                                                          "resent": True})


@require_POST
def logout_view(request):
    logout(request)
    return redirect(f"{LOGIN_URL}?out=1")


@sensitive_post_parameters("old_password", "new_password1", "new_password2")
def password_view(request):
    if not request.user.is_authenticated:
        return redirect(LOGIN_URL)
    form = PasswordChangeForm(request.user, request.POST or None)
    for f in form.fields.values():
        f.widget.attrs["class"] = "input"
    if request.method == "POST" and form.is_valid():
        user = form.save()
        user.must_change_password = False
        user.save(update_fields=["must_change_password"])
        update_session_auth_hash(request, user)
        messages.success(request, "Your password has been changed.")
        return redirect(safe_next(request, home_for(user)))
    return render(request, "web/auth/password.html", {"form": form, "forced": request.user.must_change_password,
                                                      "next": request.GET.get("next", "")})
