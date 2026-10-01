"""Everything under /api/. Each app contributes its own urls module."""
from django.urls import include, path, re_path

from apps.core.views import not_found

urlpatterns = [
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.programmes.urls")),
    path("", include("apps.admissions.urls")),
    path("", include("apps.comms.urls")),
    path("", include("apps.academics.urls")),
    path("", include("apps.payments.urls")),
    # Keep last: unknown /api/ paths return JSON, not the frontend's HTML.
    re_path(r"^.*$", not_found),
]
