from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from apps.core.views import frontend

admin.site.site_header = "TSCE Administration"
admin.site.site_title = "TSCE Admin"
admin.site.index_title = "Back office"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("config.api_urls")),
]

if settings.SERVE_FRONTEND:
    # Development only — nginx serves these in production.
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
        re_path(r"^(?P<path>.*)$", frontend),
    ]
