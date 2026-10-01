"""
Role checks for API views. These guard the server; hiding buttons in the UI is
only cosmetic. Object-level rules (a student only sees their own records) are
enforced by filtering querysets on request.user in each view.
"""
from rest_framework.permissions import BasePermission

from .models import User


class _RolePermission(BasePermission):
    roles: tuple[str, ...] = ()
    message = "You don't have permission to do that."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in self.roles)


class IsApplicant(_RolePermission):
    roles = (User.Role.APPLICANT,)


class IsStudent(_RolePermission):
    roles = (User.Role.STUDENT,)
    message = "This page is for enrolled students."


class IsPortalStaff(_RolePermission):
    """Staff or admin — the staff portal."""

    roles = (User.Role.STAFF, User.Role.ADMIN)
    message = "This page is for TSCE staff."


class IsAdmin(_RolePermission):
    roles = (User.Role.ADMIN,)
    message = "Only administrators can do that."
