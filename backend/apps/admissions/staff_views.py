"""Staff portal API for admissions: application queue, award verification, summary, search."""
import mimetypes
from datetime import timedelta

from django.db.models import Count, Q, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsPortalStaff
from apps.academics.models import Enrollment, Student
from apps.core.models import SiteSettings
from apps.payments.models import Payment

from .models import Application, AwardRequest
from .serializers import ApplicationSerializer
from .services import reject_application, send_reminder


class StaffApplicationRowSerializer(serializers.ModelSerializer):
    """One row of the staff applications table (no history — that's in the detail view)."""

    id = serializers.CharField(source="number")
    name = serializers.CharField(source="full_name")
    programmeId = serializers.CharField(source="programme.slug")
    programmeName = serializers.CharField(source="programme.name")
    intake = serializers.CharField(source="cohort.name")
    paymentStatus = serializers.CharField(source="payment_status")
    applicationFeePaidAt = serializers.DateTimeField(source="application_fee_paid_at")
    amountPayable = serializers.IntegerField(source="amount_payable")
    discountType = serializers.CharField(source="discount_type")
    account = serializers.SerializerMethodField()
    award = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(source="created_at")

    class Meta:
        model = Application
        fields = ["id", "name", "email", "phone", "programmeId", "programmeName", "intake", "status", "paymentStatus",
                  "applicationFeePaidAt", "amountPayable", "discountType", "account", "award", "createdAt"]

    def get_account(self, obj):
        u = obj.user
        return {"name": u.full_name, "email": u.email, "phone": u.phone, "type": "parent" if u.role == "parent" else "self"}

    def get_award(self, obj):
        a = getattr(obj, "award_request", None)
        return {"status": a.status, "awardedPct": a.awarded_pct, "evidence": a.evidence} if a else None


def staff_application_detail(app):
    """Full application for the staff drawer: owner view + account, payments and the WAEC file flag."""
    data = ApplicationSerializer(app).data
    u = app.user
    data["account"] = {"name": u.full_name, "email": u.email, "phone": u.phone, "type": "parent" if u.role == "parent" else "self"}
    data["payments"] = [
        {"ref": p.reference, "purpose": p.purpose, "kind": p.kind, "amount": p.amount, "status": p.status,
         "createdAt": p.created_at, "verifiedAt": p.verified_at}
        for p in app.payments.order_by("-created_at")
    ]
    data["waecFileUrl"] = f"/api/staff/applications/{app.number}/waec-file" if app.waec_file else None
    data["institution"] = app.institution
    return data


class StaffApplicationsView(APIView):
    """GET ?status=&programme=&award=&q=&from=&to= → {results, counts}."""

    permission_classes = [IsPortalStaff]

    def get(self, request):
        p = request.query_params
        qs = Application.objects.select_related("programme", "cohort", "user", "award_request")
        if p.get("programme"):
            qs = qs.filter(programme__slug=p["programme"])
        if p.get("award"):
            qs = qs.filter(award_request__isnull=False) if p["award"] == "any" else qs.filter(award_request__status=p["award"])
        if p.get("from"):
            qs = qs.filter(created_at__date__gte=p["from"])
        if p.get("to"):
            qs = qs.filter(created_at__date__lte=p["to"])
        if p.get("q"):
            q = p["q"].strip()
            qs = qs.filter(Q(number__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
                           | Q(email__icontains=q) | Q(phone__icontains=q) | Q(user__email__icontains=q)
                           | Q(user__full_name__icontains=q))
        counts = dict(qs.values_list("status").annotate(n=Count("id")))
        counts["all"] = sum(counts.values())
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        rows = StaffApplicationRowSerializer(qs.order_by("-created_at")[:2000], many=True).data
        return Response({"results": rows, "counts": counts})


def _get_app(number):
    return get_object_or_404(
        Application.objects.select_related("programme", "cohort", "user", "award_request", "enrollment__student")
        .prefetch_related("events", "payments"), number=number)


class StaffApplicationDetailView(APIView):
    permission_classes = [IsPortalStaff]

    def get(self, request, number):
        return Response(staff_application_detail(_get_app(number)))


class NoteSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class RejectApplicationView(APIView):
    permission_classes = [IsPortalStaff]

    def post(self, request, number):
        data = NoteSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        reject_application(_get_app(number), request.user, data.validated_data["note"])
        return Response(staff_application_detail(_get_app(number)))


class RemindView(APIView):
    permission_classes = [IsPortalStaff]

    def post(self, request, number):
        what = send_reminder(_get_app(number), request.user)
        return Response({"ok": True, "reminded": what})


class WaecFileView(APIView):
    """The uploaded WAEC/NECO result — private storage, staff only."""

    permission_classes = [IsPortalStaff]

    def get(self, request, number):
        app = get_object_or_404(Application, number=number)
        if not app.waec_file:
            raise Http404
        ctype = mimetypes.guess_type(app.waec_file.name)[0] or "application/octet-stream"
        ext = app.waec_file.name.rsplit(".", 1)[-1]
        resp = FileResponse(app.waec_file.open("rb"), content_type=ctype)
        resp["Content-Disposition"] = f'inline; filename="WAEC-{app.number.replace("/", "-")}.{ext}"'
        resp["X-Content-Type-Options"] = "nosniff"
        return resp


class StaffSummaryView(APIView):
    """Numbers for the staff dashboard and the sidebar badges."""

    permission_classes = [IsPortalStaff]

    def get(self, request):
        settings = SiteSettings.load()
        cohort = settings.current_cohort
        apps = Application.objects.filter(cohort=cohort) if cohort else Application.objects.none()
        by_status = dict(apps.values_list("status").annotate(n=Count("id")))
        charges = Payment.objects.filter(kind=Payment.Kind.CHARGE, status=Payment.Status.SUCCESS)
        week_ago = timezone.now() - timedelta(days=7)
        revenue = lambda qs: qs.aggregate(t=Sum("amount"))["t"] or 0  # noqa: E731
        return Response({
            "intake": cohort.name if cohort else None,
            "cohortStart": cohort.start_date if cohort else None,
            "applications": {"total": sum(by_status.values()), **by_status},
            "awardsToVerify": AwardRequest.objects.filter(status=AwardRequest.Status.PENDING,
                                                          application__status=Application.Status.AWAITING_VERIFICATION).count(),
            "enrolled": Enrollment.objects.filter(cohort=cohort).count() if cohort else 0,
            "revenue": {
                "total": revenue(charges),
                "applicationFees": revenue(charges.filter(purpose=Payment.Purpose.APPLICATION_FEE)),
                "programmeFees": revenue(charges.filter(purpose=Payment.Purpose.PROGRAMME_FEE)),
                "lastWeek": revenue(charges.filter(verified_at__gte=week_ago)),
            },
            "paymentsPending": Payment.objects.filter(kind=Payment.Kind.CHARGE, status=Payment.Status.PENDING,
                                                      created_at__gte=week_ago).count(),
            "duplicates": len(_duplicate_refs()),
            "seats": [
                {"programme": r["programme__name"], "taken": r["n"], "capacity": r["programme__capacity"]}
                for r in Enrollment.objects.filter(cohort=cohort)
                .values("programme__name", "programme__capacity").annotate(n=Count("id")).order_by("-n")
            ] if cohort else [],
        })


def _duplicate_refs():
    from apps.payments.services import counted_charge_ids

    counted = counted_charge_ids()
    return list(Payment.objects.filter(kind=Payment.Kind.CHARGE, status=Payment.Status.SUCCESS,
                                       application__isnull=False).exclude(id__in=counted)
                .values_list("reference", flat=True))


class StaffSearchView(APIView):
    """Ctrl K: applications, students and payments matching ?q= (at least 2 characters)."""

    permission_classes = [IsPortalStaff]

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        if len(q) < 2:
            return Response({"applications": [], "students": [], "payments": []})
        apps = (Application.objects.select_related("programme")
                .filter(Q(number__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
                        | Q(email__icontains=q) | Q(user__email__icontains=q) | Q(phone__icontains=q))[:6])
        students = (Student.objects.filter(Q(student_no__icontains=q) | Q(first_name__icontains=q)
                                           | Q(last_name__icontains=q) | Q(email__icontains=q))[:6])
        payments = Payment.objects.filter(Q(reference__icontains=q) | Q(name__icontains=q)
                                          | Q(application__number__icontains=q))[:6]
        return Response({
            "applications": [{"id": a.number, "name": a.full_name, "programme": a.programme.name, "status": a.status} for a in apps],
            "students": [{"id": s.student_no, "name": s.full_name} for s in students],
            "payments": [{"ref": p.reference, "name": p.name, "amount": p.amount, "status": p.status} for p in payments],
        })
