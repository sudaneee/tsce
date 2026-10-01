"""
Settings shared by every environment. Environment-specific values come from
backend/.env (see .env.example) and are overridden in dev.py / prod.py.
"""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # backend/
PROJECT_DIR = BASE_DIR.parent                             # repo root
FRONTEND_DIR = PROJECT_DIR / "frontend"

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

DEBUG = False
ALLOWED_HOSTS: list[str] = []
SERVE_FRONTEND = False  # dev.py turns this on; nginx serves frontend/ in production

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.core",
    "apps.accounts",
    "apps.programmes",
    "apps.admissions",
    "apps.payments",
    "apps.academics",
    "apps.comms",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database: SQLite tuned for a small multi-user web app ---
# WAL lets readers and a writer work concurrently; IMMEDIATE transactions take
# the write lock up front so concurrent writers wait (busy timeout) instead of
# failing with "database is locked" halfway through a transaction.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": Path(env("SQLITE_PATH", default=str(BASE_DIR / "db.sqlite3"))),
        "OPTIONS": {
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA foreign_keys=ON;",
            "transaction_mode": "IMMEDIATE",
            "timeout": 20,
        },
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Auth ---
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # 1 week
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
# The frontend reads the csrftoken cookie and sends it as X-CSRFToken.
CSRF_COOKIE_HTTPONLY = False

# --- Locale ---
LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

# --- Static & media ---
# The frontend is plain files served by nginx in production (by Django in dev).
# STATIC_* only covers Django's own assets (admin, DRF).
STATIC_URL = "/static/"
STATIC_ROOT = Path(env("STATIC_ROOT", default=str(BASE_DIR / "staticfiles")))
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", default=str(BASE_DIR / "media")))
# Personal documents (WAEC results). Never served by nginx — only via permission-checked views.
PRIVATE_MEDIA_ROOT = Path(env("PRIVATE_MEDIA_ROOT", default=str(BASE_DIR / "private_media")))
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

# --- Django REST Framework ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.core.authentication.SessionAuth"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DATETIME_FORMAT": "iso-8601",
    "DEFAULT_THROTTLE_RATES": {"login": "10/min", "register": "10/hour", "verify_email": "20/hour", "apply": "30/hour", "public_form": "20/hour", "verify": "60/min", "payment": "30/min"},
    # Number of reverse proxies in front of Django (nginx = 1 in production), so
    # throttling uses the client's real IP from X-Forwarded-For.
    "NUM_PROXIES": env.int("NUM_PROXIES", default=0),
}

# File cache: shared by all gunicorn workers without running Redis/memcached.
# Used for rate limiting (login attempts, public forms).
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": env("CACHE_DIR", default=str(BASE_DIR / ".cache")),
    }
}

# --- Email: Gmail SMTP with an app password (same setup as the Glittering project) ---
# With no EMAIL_HOST_USER, emails are printed to the console instead (development).
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_TIMEOUT = 20
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend" if EMAIL_HOST_USER else "django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default=f"TSCE <{EMAIL_HOST_USER}>" if EMAIL_HOST_USER else "TSCE <no-reply@tsce.edu.ng>")

# Public address of the site, used to build links in emails (verification, payments).
SITE_URL = env("SITE_URL", default="http://localhost:8000")
# Email-verification links stay valid this long.
EMAIL_VERIFICATION_MAX_AGE = 60 * 60 * 48

# --- Payments ---
# "simulator" for local development/demos, "zainpay" for sandbox/live.
PAYMENT_GATEWAY = env("PAYMENT_GATEWAY", default="simulator")
_ZAINPAY_ENV = env("ZAINPAY_ENVIRONMENT", default="sandbox")  # sandbox | live
ZAINPAY = {
    "ENVIRONMENT": _ZAINPAY_ENV,
    "BASE_URL": env("ZAINPAY_BASE_URL", default="https://api.zainpay.ng" if _ZAINPAY_ENV == "live" else "https://sandbox.zainpay.ng"),
    # Bearer token (JWT) from the Zainpay merchant dashboard, used for API calls.
    "PUBLIC_KEY": env("ZAINPAY_PUBLIC_KEY", default=""),
    # Only used to check the HMAC-SHA256 "Zainpay-Signature" header on webhooks.
    "SECRET_KEY": env("ZAINPAY_SECRET_KEY", default=""),
    "ZAINBOX_CODE": env("ZAINPAY_ZAINBOX_CODE", default=""),
    # Where Zainpay sends the browser back to; built from the request when empty.
    "CALLBACK_URL": env("ZAINPAY_CALLBACK_URL", default=""),
    # Flat Zainpay transaction charge (naira) paid by the payer — TSCE decision,
    # 1 Oct 2026. Added only to the amount sent to Zainpay and shown on the invoice;
    # never added to fees, payments, receipts totals or reports.
    "PAYER_CHARGE": env.int("ZAINPAY_PAYER_CHARGE", default=300),
    # Checkout channels offered by Zainpay — TSCE decision: bank transfer only.
    # Set ZAINPAY_CHANNELS= (empty) to offer everything Zainpay supports.
    "CHANNELS": env.list("ZAINPAY_CHANNELS", default=["bank_transfer"]),
    # reconcile_payments looks this far back for unconfirmed payments.
    "RECONCILE_LOOKBACK_HOURS": env.int("ZAINPAY_RECONCILE_LOOKBACK_HOURS", default=720),
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {"django": {"handlers": ["console"], "level": "INFO", "propagate": False}},
}
