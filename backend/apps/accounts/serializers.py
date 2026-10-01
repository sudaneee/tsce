"""
API field names are camelCase to match the existing frontend objects.
"""
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.core.validators import normalize_ng_phone

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
        "phone": user.phone,
        "role": user.role,
        "emailVerified": user.email_verified,
        "isAdmin": user.role == User.Role.ADMIN,
        "studentId": student.student_no if student else None,
        "staffId": staff.staff_no if staff else None,
        "applicationId": latest_app.number if latest_app else None,
        "mustChangePassword": user.must_change_password,
    }


class RegisterSerializer(serializers.Serializer):
    accountType = serializers.ChoiceField(["student", "parent"])
    fullName = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    phone = serializers.CharField(max_length=30)
    password = serializers.CharField(trim_whitespace=False, max_length=128)

    def validate_email(self, value):
        return value.strip().lower()

    def validate_phone(self, value):
        try:
            return normalize_ng_phone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))

    def validate(self, attrs):
        probe = User(email=attrs["email"], full_name=attrs["fullName"])
        try:
            password_validation.validate_password(attrs["password"], probe)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs


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
