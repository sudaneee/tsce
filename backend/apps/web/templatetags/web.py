from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def naira(amount):
    """50000 → ₦50,000"""
    try:
        return f"₦{int(amount):,}"
    except (TypeError, ValueError):
        return ""


@register.filter
def longdate(value):
    """date or datetime → 12 October 2026 (local time)"""
    if not value:
        return ""
    if hasattr(value, "hour"):
        value = timezone.localtime(value)
    return f"{value.day} {value:%B %Y}"


@register.filter
def shortdate(value):
    """→ 12 Oct 2026"""
    if not value:
        return ""
    if hasattr(value, "hour"):
        value = timezone.localtime(value)
    return f"{value.day} {value:%b %Y}"


@register.filter
def datetime_short(value):
    """→ 12 Oct 2026, 09:15"""
    if not value:
        return ""
    value = timezone.localtime(value)
    return f"{value.day} {value:%b %Y, %H:%M}"


@register.filter
def initials(name):
    parts = [p for p in str(name or "").split() if p]
    return "".join(p[0] for p in parts[:2]).upper() or "?"


@register.filter
def badge_tone(status):
    """Same colour rules as the JS UI.badge()."""
    s = str(status or "").lower()
    for tone, words in BADGE.items():
        if s in words:
            return tone
    return "primary"


BADGE = {
    "success": {"paid", "success", "enrolled", "admitted", "approved", "active", "issued", "verified", "completed", "eligible", "applied"},
    "warning": {"pending", "part paid", "awaiting verification", "processing", "requested", "pending payment"},
    "danger": {"rejected", "failed", "unpaid", "declined", "cancelled", "not eligible"},
    "info": {"refunded", "submitted"},
    "neutral": {"none", "closed", "withdrawn"},
}
