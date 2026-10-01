"""Admin-only API: staff accounts."""
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.validators import normalize_ng_phone

from . import services
from .models import StaffProfile
from .permissions import IsAdmin


class StaffSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    staffNo = serializers.CharField(source="staff_no", read_only=True)
    fullName = serializers.CharField(source="full_name")
    access = serializers.SerializerMethodField()
    userId = serializers.IntegerField(source="user_id", read_only=True)
    lastLogin = serializers.DateTimeField(source="user.last_login", read_only=True, default=None)
    joinedOn = serializers.DateField(source="joined_on", read_only=True)

    class Meta:
        model = StaffProfile
        fields = ["id", "staffNo", "fullName", "title", "department", "email", "phone", "status", "access", "userId",
                  "lastLogin", "joinedOn"]

    def get_access(self, obj):
        return services.staff_access(obj)


class StaffInputSerializer(serializers.Serializer):
    fullName = serializers.CharField(max_length=150)
    title = serializers.CharField(max_length=120)
    department = serializers.ChoiceField(StaffProfile.Department.choices)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=30, required=False, allow_blank=True, default="")
    access = serializers.ChoiceField([services.ACCESS_NONE, services.ACCESS_STAFF, services.ACCESS_ADMIN])
    status = serializers.ChoiceField(StaffProfile.Status.choices, required=False)

    def validate_email(self, value):
        return value.strip().lower()

    def validate_phone(self, value):
        if not value:
            return ""
        try:
            return normalize_ng_phone(value)
        except Exception:
            raise serializers.ValidationError("Enter a valid Nigerian phone number (e.g. 0803 123 4567).")


class StaffListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        services.ensure_staff_profiles()
        qs = StaffProfile.objects.select_related("user").order_by("staff_no")
        return Response(StaffSerializer(qs, many=True).data)

    def post(self, request):
        data = StaffInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        profile, password = services.create_staff(data.validated_data)
        return Response({"staff": StaffSerializer(profile).data, "temporaryPassword": password}, status=status.HTTP_201_CREATED)


class StaffDetailView(APIView):
    permission_classes = [IsAdmin]

    def patch(self, request, pk):
        profile = get_object_or_404(StaffProfile.objects.select_related("user"), pk=pk)
        data = StaffInputSerializer(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        changes = dict(data.validated_data)
        if profile.user_id:
            changes.pop("email", None)  # the login email isn't changed from here
        password = services.update_staff(profile, changes, request.user)
        profile.refresh_from_db()
        return Response({"staff": StaffSerializer(profile).data, "temporaryPassword": password})
