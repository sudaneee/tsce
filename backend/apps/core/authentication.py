from rest_framework.authentication import SessionAuthentication


class SessionAuth(SessionAuthentication):
    """
    Session auth that answers "not signed in" with 401 instead of DRF's default
    403 (DRF only uses 401 when the scheme has a WWW-Authenticate value). The
    frontend relies on 401 = sign in again, 403 = signed in but not allowed.
    """

    def authenticate_header(self, request):
        return 'Session realm="api"'
