from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme

LOGIN_URL = "/account/login/"


def safe_next(request, fallback: str) -> str:
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if nxt and not nxt.startswith(("/", "http:", "https:")):
        nxt = "/pages/" + nxt  # the JS portals pass e.g. "staff/payments.html" (relative to /pages/)
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return nxt
    return fallback


def applicant_required(view):
    """Signed-in applicant, parent or student account (staff go to their portal)."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect(f"{LOGIN_URL}?{urlencode({'next': request.get_full_path()})}")
        if user.is_portal_staff:
            messages.info(request, "That page is for applicants. You're signed in with a staff account.")
            return redirect("/staff/")
        if user.must_change_password:
            return redirect(f"/account/password/?{urlencode({'next': request.get_full_path()})}")
        return view(request, *args, **kwargs)
    return wrapper


def error_text(exc) -> str:
    """Message of a ServiceError (a DRF APIException)."""
    return str(exc.detail)


def error_code(exc) -> str:
    codes = exc.get_codes()
    return codes if isinstance(codes, str) else "invalid"
