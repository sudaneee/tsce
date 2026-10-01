"""
API field names are camelCase to match the existing frontend objects.
"""
from django.contrib.auth import password_validation
from rest_framework import serializers

from .models import User


def session_payload(user: User) -> dict:
    """The signed-in user as the frontend's Auth.current() expects it."""
    student = getattr(user, "student", None)
    staff = getattr(user, "staff_profile", None)
    latest_app = user.applications.order_by("-created_at").only("number").first()
    return {
        "id": user.pk,
        "email": user.email,
        "name": user.full_name,
        "role": user.role,
        "isAdmin": user.role == User.Role.ADMIN,
        "studentId": student.student_no if student else None,
        "staffId": staff.staff_no if staff else None,
        "applicationId": latest_app.number if latest_app else None,
        "mustChangePassword": user.must_change_password,
    }


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False)
    remember = serializers.BooleanField(default=True)


class ChangePasswordSerializer(serializers.Serializer):
    currentPassword = serializers.CharField(trim_whitespace=False)
    newPassword = serializers.CharField(trim_whitespace=False, min_length=8)

    def validate_currentPassword(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Your current password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs["currentPassword"] == attrs["newPassword"]:
            raise serializers.ValidationError({"newPassword": "Choose a password different from your current one."})
        try:
            password_validation.validate_password(attrs["newPassword"], self.context["request"].user)
        except Exception as exc:  # django.core.exceptions.ValidationError
            raise serializers.ValidationError({"newPassword": list(exc.messages)})
        return attrs
