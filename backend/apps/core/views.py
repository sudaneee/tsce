from django.conf import settings
from django.db import connection
from django.http import Http404
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.static import serve
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    """Liveness check for the frontend and the VPS monitor."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return Response({"status": "ok", "time": timezone.now()})


@ensure_csrf_cookie
@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
    """Sets the csrftoken cookie; the frontend calls this before its first POST."""
    return Response({"csrfToken": get_token(request)})


@api_view(["GET", "POST", "PUT", "PATCH", "DELETE"])
@permission_classes([AllowAny])
def not_found(request):
    raise Http404


def frontend(request, path):
    """Development only: serve frontend/ files, mapping folders to index.html."""
    if path == "" or path.endswith("/"):
        path += "index.html"
    return serve(request, path, document_root=settings.FRONTEND_DIR)
