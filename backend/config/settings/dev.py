"""Local development: python manage.py runserver → http://localhost:8000"""
from .base import *  # noqa: F401,F403
from .base import REST_FRAMEWORK, env

DEBUG = True
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-only-insecure-key-do-not-use-in-production")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Django serves the frontend files and uploads itself in development.
SERVE_FRONTEND = True

REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}
