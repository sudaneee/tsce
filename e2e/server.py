"""
Dev server for the browser tests with "today" pinned (E2E_TODAY, default 2026-10-01),
so the admissions calendar (application window, early bird) doesn't depend on the
real date. Run from backend/:  python ../e2e/server.py <port>
"""
import os
import sys
from datetime import date

from django.utils import timezone

TODAY = date.fromisoformat(os.environ.get("E2E_TODAY", "2026-10-01"))
_localdate = timezone.localdate
timezone.localdate = lambda value=None, timezone=None: TODAY if value is None else _localdate(value, timezone)

sys.path.insert(0, os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
from django.core.management import execute_from_command_line  # noqa: E402

execute_from_command_line(["manage.py", "runserver", sys.argv[1], "--noreload"])
