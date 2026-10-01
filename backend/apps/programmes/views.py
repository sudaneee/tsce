from django.conf import settings as dj_settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.admissions.discounts import admissions_state, early_bird_open, seats_taken, today
from apps.core.models import SiteSettings

from .models import Programme
from .serializers import ProgrammeSerializer


def public_settings(s: SiteSettings) -> dict:
    cohort = s.current_cohort
    state = admissions_state(s)
    channels = dj_settings.ZAINPAY["CHANNELS"]
    iso = lambda d: d.isoformat() if d else None  # noqa: E731
    return {
        "institution": {
            "name": s.institution_name, "short": s.short_name, "address": s.address, "city": s.city,
            "phones": s.phones, "email": s.email, "website": s.website,
            "directorName": s.director_name, "directorTitle": s.director_title,
        },
        "admissions": {
            "intake": cohort.name if cohort else None,
            "cohortDate": iso(cohort and cohort.start_date),
            "opens": iso(cohort and cohort.enrolment_opens),
            "closes": iso(cohort and cohort.enrolment_closes),
            "earlyBirdDeadline": iso(cohort and cohort.early_bird_deadline),
            "acceptingApplications": s.accepting_applications,
            "open": state.open,
            "closedMessage": state.message,
        },
        "discounts": {
            "earlybird": s.early_bird_pct, "excellence": s.excellence_pct, "scholarshipMax": s.scholarship_max_pct,
            "excellenceMinYear": s.excellence_min_waec_year, "excellenceMinAs": s.excellence_min_as,
            "earlyBirdOpen": early_bird_open(cohort),
        },
        "payments": {
            # Zainpay channel restrictions (settings) win over the admin toggles.
            "allowCard": s.allow_card and (not channels or any("card" in c for c in channels)),
            "allowTransfer": s.allow_transfer and (not channels or any("transfer" in c for c in channels)),
            "payerCharge": dj_settings.ZAINPAY["PAYER_CHARGE"],
            "gateway": dj_settings.PAYMENT_GATEWAY,
            "environment": "simulated" if dj_settings.PAYMENT_GATEWAY == "simulator" else dj_settings.ZAINPAY["ENVIRONMENT"],
        },
        "today": today().isoformat(),
    }


class SiteView(APIView):
    """
    Everything every page needs, in one request: public settings + the
    programme catalogue (active only for visitors; all for staff).
    """

    permission_classes = [AllowAny]

    def get(self, request):
        settings = SiteSettings.load()
        qs = Programme.objects.select_related("instructor").prefetch_related("modules")
        if not (request.user.is_authenticated and request.user.is_portal_staff):
            qs = qs.filter(status=Programme.Status.ACTIVE)
        context = {"seats_taken": seats_taken(settings.current_cohort)}
        return Response({
            "settings": public_settings(settings),
            "programmes": ProgrammeSerializer(qs, many=True, context=context).data,
        })
