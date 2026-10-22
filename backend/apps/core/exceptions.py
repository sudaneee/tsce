"""Business-rule failures raised by services and shown by the views."""


class ServiceError(Exception):
    """A rule the request broke (e.g. "already paid"). `code` is stable for tests and branching."""

    def __init__(self, message, code="invalid", *, field=None, extra=None, status_code=400):
        super().__init__(message)
        self.message = str(message)
        self.code = code
        self.field = field
        self.extra = extra or {}
        self.status_code = status_code

    def __str__(self):
        return self.message
