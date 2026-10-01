from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsPortalStaff

from .models import Application
from .serializers import ApplicationCreateSerializer, ApplicationSerializer
from .services import create_application, review_award


def _with_relations(qs):
    return (qs.select_related("programme", "cohort", "award_request", "enrollment__student")
            .prefetch_related("events", "payments"))


class ApplicationsView(APIView):
    """
    GET  → the signed-in account's applications (a parent sees every child's).
    POST → apply (multipart). The account must have a verified email.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "apply"

    def get_throttles(self):
        return super().get_throttles() if self.request.method == "POST" else []

    def get(self, request):
        apps = _with_relations(Application.objects.filter(user=request.user).order_by("-created_at"))
        return Response(ApplicationSerializer(apps, many=True).data)

    def post(self, request):
        data = ApplicationCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        app = create_application(data.validated_data, request.user)
        return Response(ApplicationSerializer(app).data, status=status.HTTP_201_CREATED)


class ApplicationDetailView(APIView):
    """An application by number — for the account that owns it, or for staff."""

    permission_classes = [IsAuthenticated]

    def get(self, request, number):
        qs = _with_relations(Application.objects.all())
        if not request.user.is_portal_staff:
            qs = qs.filter(user=request.user)  # others' applications simply don't exist
        return Response(ApplicationSerializer(get_object_or_404(qs, number=number)).data)


class AwardDecisionSerializer(serializers.Serializer):
    approve = serializers.BooleanField()
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class AwardDecisionView(APIView):
    """Staff: POST {approve, note} after seeing the WAEC/NECO result in person. Admits either way."""

    permission_classes = [IsPortalStaff]

    def post(self, request, number):
        app = get_object_or_404(Application, number=number)
        data = AwardDecisionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        app = review_award(app, data.validated_data["approve"], request.user, data.validated_data["note"])
        return Response(ApplicationSerializer(_with_relations(Application.objects.all()).get(pk=app.pk)).data)
