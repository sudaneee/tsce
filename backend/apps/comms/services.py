"""In-app notifications, optionally emailed too (see notify(email=True))."""
from apps.accounts.models import User

from .models import Notification


def notify(user, title, body, type=Notification.Type.ANNOUNCEMENT, link="", email=False):
    """In-app notification; with email=True it is also emailed (if email notifications are on)."""
    if user is None:
        return None
    note = Notification.objects.create(recipient=user, title=title, body=body, type=type, link=link)
    if email:
        from apps.core.emails import send_email, site_link
        from apps.core.models import SiteSettings

        if SiteSettings.load().email_notifications:
            text = f"Dear {user.full_name},\n\n{body}"
            if link:
                text += f"\n\n{site_link(link)}"
            send_email(f"TSCE: {title}", text, user.email)
    return note


def notify_staff(title, body, type=Notification.Type.ANNOUNCEMENT, link=""):
    """Fan out to every active staff/admin user, so each has their own read state."""
    staff = User.objects.filter(is_active=True, role__in=[User.Role.STAFF, User.Role.ADMIN]).only("pk")
    Notification.objects.bulk_create(
        [Notification(recipient=u, title=title, body=body, type=type, link=link) for u in staff]
    )
