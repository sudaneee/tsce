from django.urls import path

from . import staff_views, views

urlpatterns = [
    path("health", views.health, name="health"),
    path("auth/csrf", views.csrf, name="csrf"),
    path("staff/settings", staff_views.SettingsView.as_view(), name="staff-settings"),
    path("staff/intakes", staff_views.NewIntakeView.as_view(), name="staff-new-intake"),
]
