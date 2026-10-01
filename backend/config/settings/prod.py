"""Production (VPS behind nginx). All secrets come from backend/.env."""
from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# nginx serves frontend/, /static/ and /media/ directly.
SERVE_FRONTEND = False

# HTTPS is terminated by nginx, which sets X-Forwarded-Proto.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Start low; raise to 31536000 once HTTPS is confirmed stable on the domain.
SECURE_HSTS_SECONDS = env.int("DJANGO_HSTS_SECONDS", default=3600)
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
