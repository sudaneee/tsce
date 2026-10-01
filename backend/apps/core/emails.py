"""
Best-effort email, same pattern as the Glittering project (communication/emails.py):
plain send_mail wrapped in try/except, so a bad address or a mail-server outage is
logged and never breaks the request, webhook or cron job that triggered it.
"""
import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

SIGNATURE = "\n\n— Trust Skills Center of Excellence (TSCE), Zaria"


def site_link(path: str) -> str:
    """Absolute link to a frontend page, e.g. site_link('pages/login.html')."""
    return settings.SITE_URL.rstrip("/") + "/" + path.lstrip("/")


def send_email(subject: str, message: str, to_email: str) -> bool:
    if not to_email:
        logger.info('send_email: no recipient for "%s" — skipped.', subject)
        return False
    try:
        send_mail(subject=subject, message=message + SIGNATURE, from_email=settings.DEFAULT_FROM_EMAIL,
                  recipient_list=[to_email], fail_silently=False)
        return True
    except Exception:
        logger.exception('Failed to send email "%s" to %s', subject, to_email)
        return False
