from django.urls import path

from . import views

urlpatterns = [
    path("applications", views.ApplicationCreateView.as_view(), name="application-create"),
    # Numbers contain slashes (TSCE/APP/2026/00001), hence <path:>.
    path("applications/<path:number>", views.ApplicationDetailView.as_view(), name="application-detail"),
]
