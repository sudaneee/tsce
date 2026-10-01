"""
Every API error has the same JSON shape, which js/api.js relies on:

    {"error": "Human-readable message", "code": "machine_code", "fields": {"email": ["…"]}}

A ServiceError may add an "extra" object with data the UI can act on
(e.g. the number of an existing application to continue with).
"""
import logging

from django.conf import settings
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class ServiceError(exceptions.APIException):
    """A business-rule failure raised by a service (400 unless stated)."""

    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "invalid"

    def __init__(self, message, code="invalid", *, field=None, extra=None, status_code=None):
        super().__init__(message, code)
        self.field = field
        self.extra = extra or {}
        if status_code:
            self.status_code = status_code


def _messages(detail):
    """Flattens DRF error detail (str / list / dict, possibly nested) to a list of strings."""
    if isinstance(detail, dict):
        return [m for v in detail.values() for m in _messages(v)]
    if isinstance(detail, list):
        return [m for v in detail for m in _messages(v)]
    return [str(detail)]


def api_exception_handler(exc, context):
    # Same conversion DRF does internally, done here so we keep the DRF error code.
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)

    if response is None:
        # Unhandled error: let Django show the traceback while developing.
        if settings.DEBUG:
            return None
        logger.exception("Unhandled API error", exc_info=exc)
        return Response(
            {"error": "Something went wrong on our side. Please try again.", "code": "server_error", "fields": {}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    detail = response.data
    if isinstance(exc, ValidationError):
        fields = detail if isinstance(detail, dict) else {"non_field_errors": detail}
        fields = {k: _messages(v) for k, v in fields.items()}
        message = next(iter(_messages(detail)), "Please check the highlighted fields.")
        code = "invalid"
    else:
        fields = {}
        message = str(detail.get("detail", detail)) if isinstance(detail, dict) else str(detail)
        code = getattr(exc, "default_code", "error")
        codes = exc.get_codes() if hasattr(exc, "get_codes") else None
        if isinstance(codes, str):
            code = codes

    response.data = {"error": message, "code": code, "fields": fields}
    if isinstance(exc, ServiceError):
        if exc.field:
            response.data["fields"] = {exc.field: [message]}
        if exc.extra:
            response.data["extra"] = exc.extra
    return response
