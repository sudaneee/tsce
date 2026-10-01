from django.urls import path, re_path

from . import views

urlpatterns = [
    path("health", views.health, name="health"),
    path("auth/csrf", views.csrf, name="csrf"),
    # Keep this last: unknown /api/ paths return JSON, not the frontend's HTML.
    re_path(r"^.*$", views.not_found),
]
