from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.models import SiteSettings
from apps.core.validators import normalize_ng_phone

from .models import Announcement, Enquiry, Notification
from .services import notify_staff


class EnquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = Enquiry
        fields = ["name", "email", "phone", "programme", "subject", "message"]
        extra_kwargs = {"message": {"min_length": 10}}

    def validate_phone(self, value):
        if not value:
            return ""
        try:
            return normalize_ng_phone(value)
        except Exception:
            raise serializers.ValidationError("Enter a valid Nigerian phone number (e.g. 0803 123 4567).")


@method_decorator(csrf_protect, name="dispatch")
class EnquiryCreateView(APIView):
    """The public contact form."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "public_form"

    def post(self, request):
        data = EnquirySerializer(data=request.data)
        data.is_valid(raise_exception=True)
        enquiry = data.save()
        notify_staff("New enquiry", f"{enquiry.name}: {enquiry.subject or enquiry.programme or 'General enquiry'}",
                     Notification.Type.SUPPORT)
        return Response({"ok": True}, status=status.HTTP_201_CREATED)


class PublicAnnouncementSerializer(serializers.ModelSerializer):
    author = serializers.SerializerMethodField()
    createdAt = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = ["id", "title", "body", "tag", "pinned", "author", "createdAt"]

    def get_author(self, obj):
        return obj.author_label or SiteSettings.load().short_name

    def get_createdAt(self, obj):
        return obj.published_at or obj.created_at


class PublicAnnouncementsView(APIView):
    """Published announcements for the public News page."""

    permission_classes = [AllowAny]

    def get(self, request):
        qs = Announcement.objects.filter(status=Announcement.Status.PUBLISHED, audience=Announcement.Audience.PUBLIC)
        return Response(PublicAnnouncementSerializer(qs[:50], many=True).data)
