"""
Go-live checklist for a server:  python manage.py preflight [--send-test-email you@example.com]

Prints ✔ / ⚠ / ✘ per check and exits 1 if anything is ✘, so it can gate a deploy.
"""
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

OK, WARN, FAIL = "ok", "warn", "fail"


class Command(BaseCommand):
    help = "Check that this server is ready for real applicants and payments."

    def add_arguments(self, parser):
        parser.add_argument("--send-test-email", metavar="ADDRESS", help="Also send a test email to ADDRESS.")

    def handle(self, *args, send_test_email=None, **options):
        self.results = []
        self.check_django()
        self.check_database()
        self.check_school()
        self.check_payments()
        self.check_email(send_test_email)
        self.check_files()

        marks = {OK: self.style.SUCCESS("  ✔ "), WARN: self.style.WARNING("  ⚠ "), FAIL: self.style.ERROR("  ✘ ")}
        section = None
        for sec, level, text in self.results:
            if sec != section:
                self.stdout.write(f"\n{sec}")
                section = sec
            self.stdout.write(marks[level] + text)
        fails = sum(1 for _, lvl, _ in self.results if lvl == FAIL)
        warns = sum(1 for _, lvl, _ in self.results if lvl == WARN)
        self.stdout.write("")
        summary = f"{fails} problem(s), {warns} warning(s)."
        if fails:
            self.stdout.write(self.style.ERROR("NOT READY — " + summary))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("READY — " + summary))

    def add(self, section, ok, good, bad, level_if_bad=FAIL):
        self.results.append((section, OK if ok else level_if_bad, good if ok else bad))

    # --- checks -------------------------------------------------------------
    def check_django(self):
        S = "Django"
        self.add(S, not settings.DEBUG, "DEBUG is off", "DEBUG is ON — never run a public site with DEBUG=True")
        key = settings.SECRET_KEY or ""
        self.add(S, len(key) >= 40 and "insecure" not in key and "change-me" not in key,
                 "SECRET_KEY looks strong", "DJANGO_SECRET_KEY is missing, short or a placeholder")
        site = urlparse(settings.SITE_URL)
        self.add(S, site.scheme == "https", f"SITE_URL uses HTTPS ({settings.SITE_URL})",
                 f"SITE_URL should be https://… (now {settings.SITE_URL}) — email links use it")
        self.add(S, site.hostname in settings.ALLOWED_HOSTS, f"{site.hostname} is in DJANGO_ALLOWED_HOSTS",
                 f"DJANGO_ALLOWED_HOSTS should include {site.hostname} (now {settings.ALLOWED_HOSTS})")
        origin = f"{site.scheme}://{site.netloc}"
        self.add(S, origin in getattr(settings, "CSRF_TRUSTED_ORIGINS", []), f"{origin} is a trusted CSRF origin",
                 f"Add {origin} to DJANGO_CSRF_TRUSTED_ORIGINS")
        self.add(S, settings.REST_FRAMEWORK.get("NUM_PROXIES") == 1, "NUM_PROXIES=1 (real client IPs behind nginx)",
                 "Set NUM_PROXIES=1 so rate limits see real client IPs, not nginx", WARN)
        self.add(S, bool(getattr(settings, "SESSION_COOKIE_SECURE", False)), "Secure cookies on", "SESSION_COOKIE_SECURE is off")

    def check_database(self):
        S = "Database"
        try:
            with connection.cursor() as c:
                c.execute("PRAGMA journal_mode")
                mode = c.fetchone()[0]
            self.add(S, mode.lower() == "wal", "SQLite in WAL mode", f"SQLite journal mode is {mode}, expected wal", WARN)
        except Exception as exc:
            self.add(S, False, "", f"Can't open the database: {exc}")
            return
        plan = MigrationExecutor(connection).migration_plan(MigrationExecutor(connection).loader.graph.leaf_nodes())
        self.add(S, not plan, "All migrations applied", f"{len(plan)} migration(s) not applied — run: python manage.py migrate")
        db = Path(settings.DATABASES["default"]["NAME"])
        self.add(S, os.access(db.parent, os.W_OK), f"Database folder writable ({db.parent})",
                 f"{db.parent} is not writable by this user (SQLite needs it for the WAL files)")

    def check_school(self):
        from apps.accounts.models import User
        from apps.core.models import SiteSettings
        from apps.programmes.models import Programme

        S = "School data"
        s = SiteSettings.objects.select_related("current_cohort").filter(pk=1).first()
        self.add(S, s is not None, "Site settings exist", "No site settings — run: python manage.py seed_school")
        if s:
            self.add(S, s.current_cohort is not None, f"Current intake: {s.current_cohort}", "No current intake (Staff → Settings)")
            self.add(S, bool(s.director_name), f"Director for certificates: {s.director_name}",
                     "Director's name is empty (Staff → Settings → Institution) — certificates print it", WARN)
            c = s.current_cohort
            if c and c.enrolment_opens and c.early_bird_deadline:
                self.add(S, c.early_bird_deadline > c.enrolment_opens, "Early-bird deadline is after applications open",
                         f"Early bird ends {c.early_bird_deadline} but applications only open {c.enrolment_opens} — nobody can get it", WARN)
        n = Programme.objects.filter(status=Programme.Status.ACTIVE).count()
        self.add(S, n > 0, f"{n} active programmes", "No active programmes — run: python manage.py seed_school")
        admins = User.objects.filter(role=User.Role.ADMIN, is_active=True).count()
        self.add(S, admins > 0, f"{admins} admin account(s)", "No admin account — run: python manage.py createsuperuser")

    def check_payments(self):
        S = "Payments"
        zp = settings.ZAINPAY
        gw = settings.PAYMENT_GATEWAY
        self.add(S, gw == "zainpay", "Gateway: Zainpay", f"PAYMENT_GATEWAY={gw} — applicants can't really pay", FAIL)
        if gw != "zainpay":
            return
        self.add(S, bool(zp["PUBLIC_KEY"]), "ZAINPAY_PUBLIC_KEY set", "ZAINPAY_PUBLIC_KEY is empty")
        self.add(S, bool(zp["ZAINBOX_CODE"]), "ZAINPAY_ZAINBOX_CODE set", "ZAINPAY_ZAINBOX_CODE is empty")
        self.add(S, bool(zp["SECRET_KEY"]), "ZAINPAY_SECRET_KEY set (webhooks are signature-checked)",
                 "ZAINPAY_SECRET_KEY is empty — webhook signatures can't be checked", WARN)
        self.add(S, zp["ENVIRONMENT"] == "live", "Environment: live", f"Environment: {zp['ENVIRONMENT']} — no real money until 'live'", WARN)
        cb = zp["CALLBACK_URL"] or f"{settings.SITE_URL.rstrip('/')}/api/payments/zainpay/callback"
        self.add(S, cb.startswith("https://"), f"Callback URL {cb}", f"Callback URL should be https ({cb})")
        self.results.append((S, OK, f"Register this webhook in the Zainpay dashboard: {settings.SITE_URL.rstrip('/')}/api/payments/zainpay/webhook"))
        self.results.append((S, OK, f"Payer charge ₦{zp['PAYER_CHARGE']}; channels: {', '.join(zp['CHANNELS']) or 'all'}"))

    def check_email(self, to):
        S = "Email"
        smtp = settings.EMAIL_BACKEND.endswith("smtp.EmailBackend")
        self.add(S, smtp and bool(settings.EMAIL_HOST_USER), f"SMTP as {settings.EMAIL_HOST_USER}",
                 "Email is not configured (EMAIL_HOST_USER / EMAIL_HOST_PASSWORD) — nobody can verify their email")
        if to:
            try:
                send_mail("TSCE preflight test", "If you can read this, outgoing email works.", settings.DEFAULT_FROM_EMAIL, [to])
                self.add(S, True, f"Test email sent to {to} — check the inbox (and spam)", "")
            except Exception as exc:
                self.add(S, False, "", f"Sending failed: {exc}")

    def check_files(self):
        S = "Files"
        private = Path(settings.PRIVATE_MEDIA_ROOT).resolve()
        try:
            private.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=private):
                pass
            self.add(S, True, f"Private uploads writable ({private})", "")
        except OSError as exc:
            self.add(S, False, "", f"Private uploads folder not writable ({private}): {exc}")
        public_roots = [Path(settings.STATIC_ROOT).resolve(), Path(settings.MEDIA_ROOT).resolve(), Path(settings.FRONTEND_DIR).resolve()]
        exposed = any(private == r or r in private.parents for r in public_roots)
        self.add(S, not exposed, "Private uploads are outside every public folder",
                 f"PRIVATE_MEDIA_ROOT ({private}) is inside a folder nginx serves — WAEC results would be public")
        admin_css = Path(settings.STATIC_ROOT) / "admin" / "css" / "base.css"
        self.add(S, admin_css.exists(), f"Static files collected ({settings.STATIC_ROOT})",
                 "Static files missing — run: python manage.py collectstatic --noinput", WARN)
        cache = Path(settings.CACHES["default"]["LOCATION"])
        try:
            cache.mkdir(parents=True, exist_ok=True)
            self.add(S, os.access(cache, os.W_OK), f"Cache folder writable ({cache})", f"{cache} is not writable (rate limiting needs it)")
        except OSError as exc:
            self.add(S, False, "", f"Cache folder problem: {exc}")
