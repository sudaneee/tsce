from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.static import serve


@require_GET
def health(request):
    """Liveness check used by the update script and the VPS monitor."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"status": "ok", "time": timezone.now().isoformat()})


def not_found(request):
    return JsonResponse({"error": "Not found", "code": "not_found"}, status=404)


def frontend(request, path):
    """Development only: serve frontend/ files, mapping folders to index.html."""
    if path == "" or path.endswith("/"):
        path += "index.html"
    return serve(request, path, document_root=settings.FRONTEND_DIR)
