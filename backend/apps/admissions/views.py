from django.contrib.auth import login
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.serializers import session_payload

from .models import Application
from .serializers import ApplicationCreateSerializer, ApplicationSerializer
from .services import create_application


# CSRF enforced although visitors are anonymous: this view signs the applicant in.
@method_decorator(csrf_protect, name="dispatch")
@method_decorator(sensitive_post_parameters("password"), name="dispatch")
class ApplicationCreateView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "apply"

    def post(self, request):
        data = ApplicationCreateSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        app = create_application(data.validated_data, request.user)
        if not request.user.is_authenticated:
            # Signed in straight away so they can pay now or come back later.
            login(request, app.user, backend="django.contrib.auth.backends.ModelBackend")
        return Response(
            {"application": ApplicationSerializer(app).data, "user": session_payload(app.user)},
            status=status.HTTP_201_CREATED,
        )


class ApplicationDetailView(APIView):
    """An application by number — for its owner, or for staff."""

    permission_classes = [IsAuthenticated]

    def get(self, request, number):
        qs = Application.objects.select_related("programme", "cohort", "award_request").prefetch_related("events")
        if not request.user.is_portal_staff:
            qs = qs.filter(user=request.user)  # others' applications simply don't exist
        return Response(ApplicationSerializer(get_object_or_404(qs, number=number)).data)
