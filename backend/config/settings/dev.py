"""Local development: python manage.py runserver → http://localhost:8000"""
from .base import *  # noqa: F401,F403
from .base import env

DEBUG = True
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-insecure-key-do-not-use-in-production")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Django serves the frontend files and uploads itself in development.
SERVE_FRONTEND = True


# Tests: a fast hasher (the real one is deliberately slow, ~1s per login).
import sys  # noqa: E402

if "test" in sys.argv:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    BACKGROUND_TASKS_INLINE = True
