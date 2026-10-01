"""Admin-only API: site settings and intakes (cohorts)."""
from django.conf import settings as dj_settings
from django.db import transaction
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin, IsPortalStaff

from .exceptions import ServiceError
from .models import SiteSettings


def settings_payload(s: SiteSettings) -> dict:
    c = s.current_cohort
    return {
        "institution": {"name": s.institution_name, "short": s.short_name, "address": s.address, "city": s.city,
                        "phones": s.phones, "email": s.email, "website": s.website,
                        "directorName": s.director_name, "directorTitle": s.director_title},
        "admissions": {"intake": c.name if c else "", "cohortDate": c and c.start_date, "opens": c and c.enrolment_opens,
                       "closes": c and c.enrolment_closes, "earlyBirdDeadline": c and c.early_bird_deadline,
                       "acceptingApplications": s.accepting_applications, "applicationFee": s.application_fee},
        "discounts": {"earlyBirdPct": s.early_bird_pct, "excellencePct": s.excellence_pct,
                      "excellenceMinYear": s.excellence_min_waec_year, "excellenceMinAs": s.excellence_min_as},
        "notifications": {"emailNotifications": s.email_notifications, "staffPaymentAlerts": s.staff_payment_alerts,
                          "staffApplicationAlerts": s.staff_application_alerts},
        # Read-only: these live in backend/.env on the server.
        "gateway": {"name": dj_settings.PAYMENT_GATEWAY, "environment": dj_settings.ZAINPAY["ENVIRONMENT"],
                    "payerCharge": dj_settings.ZAINPAY["PAYER_CHARGE"], "channels": dj_settings.ZAINPAY["CHANNELS"],
                    "refPrefix": s.payment_ref_prefix, "emailConfigured": bool(dj_settings.EMAIL_HOST_USER)},
    }


class InstitutionSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    short = serializers.CharField(max_length=20)
    address = serializers.CharField(max_length=300)
    city = serializers.CharField(max_length=120, required=False, allow_blank=True)
    phones = serializers.ListField(child=serializers.CharField(max_length=30), max_length=6)
    email = serializers.EmailField(required=False, allow_blank=True)
    website = serializers.CharField(max_length=120, required=False, allow_blank=True)
    directorName = serializers.CharField(max_length=120, required=False, allow_blank=True)
    directorTitle = serializers.CharField(max_length=120, required=False, allow_blank=True)


class AdmissionsSerializer(serializers.Serializer):
    intake = serializers.CharField(max_length=80)
    cohortDate = serializers.DateField()
    opens = serializers.DateField(allow_null=True, required=False)
    closes = serializers.DateField(allow_null=True, required=False)
    earlyBirdDeadline = serializers.DateField(allow_null=True, required=False)
    acceptingApplications = serializers.BooleanField()
    applicationFee = serializers.IntegerField(min_value=0, max_value=1_000_000)

    def validate(self, a):
        if a.get("opens") and a.get("closes") and a["opens"] > a["closes"]:
            raise serializers.ValidationError({"closes": "The closing date must be after the opening date."})
        if a.get("closes") and a["closes"] > a["cohortDate"]:
            raise serializers.ValidationError({"closes": "Applications should close on or before the cohort start date."})
        return a


class DiscountsSerializer(serializers.Serializer):
    earlyBirdPct = serializers.IntegerField(min_value=0, max_value=100)
    excellencePct = serializers.IntegerField(min_value=0, max_value=100)
    excellenceMinYear = serializers.IntegerField(min_value=2000, max_value=2100)
    excellenceMinAs = serializers.IntegerField(min_value=1, max_value=9)


class NotificationsSerializer(serializers.Serializer):
    emailNotifications = serializers.BooleanField()
    staffPaymentAlerts = serializers.BooleanField()
    staffApplicationAlerts = serializers.BooleanField()


SECTIONS = {"institution": InstitutionSerializer, "admissions": AdmissionsSerializer,
            "discounts": DiscountsSerializer, "notifications": NotificationsSerializer}


class SettingsView(APIView):
    """GET (any staff, read) / PATCH {section: {...}} (admin). One section per request."""

    def get_permissions(self):
        return [IsAdmin()] if self.request.method == "PATCH" else [IsPortalStaff()]

    def get(self, request):
        return Response(settings_payload(SiteSettings.load()))

    @transaction.atomic
    def patch(self, request):
        s = SiteSettings.load()
        unknown = set(request.data) - set(SECTIONS)
        if unknown or not request.data:
            raise ServiceError("Send one of: " + ", ".join(SECTIONS), "invalid")
        for section, payload in request.data.items():
            ser = SECTIONS[section](data=payload)
            if not ser.is_valid():
                raise serializers.ValidationError(ser.errors)
            d = ser.validated_data
            if section == "institution":
                s.institution_name, s.short_name, s.address = d["name"], d["short"], d["address"]
                s.city, s.phones, s.email = d.get("city", ""), d["phones"], d.get("email", "")
                s.website, s.director_name = d.get("website", ""), d.get("directorName", "")
                s.director_title = d.get("directorTitle", "") or s.director_title
            elif section == "admissions":
                c = s.current_cohort
                if c is None:
                    raise ServiceError("There is no current intake. Start a new intake first.", "no_cohort")
                c.name, c.start_date = d["intake"], d["cohortDate"]
                c.enrolment_opens, c.enrolment_closes = d.get("opens"), d.get("closes")
                c.early_bird_deadline = d.get("earlyBirdDeadline")
                c.save()
                s.accepting_applications, s.application_fee = d["acceptingApplications"], d["applicationFee"]
            elif section == "discounts":
                s.early_bird_pct, s.excellence_pct = d["earlyBirdPct"], d["excellencePct"]
                s.excellence_min_waec_year, s.excellence_min_as = d["excellenceMinYear"], d["excellenceMinAs"]
            elif section == "notifications":
                s.email_notifications = d["emailNotifications"]
                s.staff_payment_alerts, s.staff_application_alerts = d["staffPaymentAlerts"], d["staffApplicationAlerts"]
        s.save()
        return Response(settings_payload(SiteSettings.load()))


class NewIntakeSerializer(serializers.Serializer):
    intake = serializers.CharField(max_length=80)
    cohortDate = serializers.DateField()
    opens = serializers.DateField(allow_null=True, required=False)
    closes = serializers.DateField(allow_null=True, required=False)
    earlyBirdDeadline = serializers.DateField(allow_null=True, required=False)


class NewIntakeView(APIView):
    """Start the next intake: creates a cohort and makes it current. Earlier applications keep theirs."""

    permission_classes = [IsAdmin]

    @transaction.atomic
    def post(self, request):
        from apps.programmes.models import Cohort

        data = NewIntakeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        d = data.validated_data
        if Cohort.objects.filter(name__iexact=d["intake"]).exists():
            raise ServiceError("An intake with that name already exists.", "invalid", field="intake")
        cohort = Cohort.objects.create(name=d["intake"], start_date=d["cohortDate"], enrolment_opens=d.get("opens"),
                                       enrolment_closes=d.get("closes"), early_bird_deadline=d.get("earlyBirdDeadline"))
        s = SiteSettings.load()
        s.current_cohort = cohort
        s.save(update_fields=["current_cohort", "updated_at"])
        return Response(settings_payload(s), status=status.HTTP_201_CREATED)
