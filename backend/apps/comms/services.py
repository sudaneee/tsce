"""In-app notifications. Email delivery is added in Phase 10, once TSCE has a mailbox."""
from apps.accounts.models import User

from .models import Notification


def notify(user, title, body, type=Notification.Type.ANNOUNCEMENT, link=""):
    if user is None:
        return None
    return Notification.objects.create(recipient=user, title=title, body=body, type=type, link=link)


def notify_staff(title, body, type=Notification.Type.ANNOUNCEMENT, link=""):
    """Fan out to every active staff/admin user, so each has their own read state."""
    staff = User.objects.filter(is_active=True, role__in=[User.Role.STAFF, User.Role.ADMIN]).only("pk")
    Notification.objects.bulk_create(
        [Notification(recipient=u, title=title, body=body, type=type, link=link) for u in staff]
    )
