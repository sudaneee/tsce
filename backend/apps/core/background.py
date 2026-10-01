"""
Tiny fire-and-forget helper for work that shouldn't hold up a response:
sending email, and processing a Zainpay webhook after acknowledging it.

Runs in a daemon thread (gunicorn uses threads). If the process restarts before
the work finishes, nothing is corrupted: payments are re-checked by the
reconcile_payments timer, and at worst an email isn't sent. Tests run the work
inline (BACKGROUND_TASKS_INLINE) so they stay deterministic.
"""
import logging
import threading

from django.conf import settings
from django.db import close_old_connections, connection

logger = logging.getLogger(__name__)


def run_in_background(fn, *args, **kwargs):
    if getattr(settings, "BACKGROUND_TASKS_INLINE", False):
        fn(*args, **kwargs)
        return

    def target():
        try:
            close_old_connections()
            fn(*args, **kwargs)
        except Exception:
            logger.exception("Background task %s failed", getattr(fn, "__name__", fn))
        finally:
            connection.close()  # each thread has its own DB connection

    threading.Thread(target=target, daemon=True, name=f"bg-{getattr(fn, '__name__', 'task')}").start()
