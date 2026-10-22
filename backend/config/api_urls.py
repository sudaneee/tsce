"""What remains under /api/: the health check and Zainpay's endpoints."""
from django.urls import include, path, re_path

from apps.core.views import not_found

urlpatterns = [
    path("", include("apps.core.urls")),
    path("", include("apps.payments.urls")),
    re_path(r"^.*$", not_found),
]
