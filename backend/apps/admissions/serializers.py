from datetime import date

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.core.validators import normalize_ng_phone, validate_document
from apps.programmes.models import Programme

from .discounts import today
from .models import Application, AwardRequest

STATES = [
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue", "Borno", "Cross River", "Delta",
    "Ebonyi", "Edo", "Ekiti", "Enugu", "FCT", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi",
    "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers", "Sokoto",
    "Taraba", "Yobe", "Zamfara",
]
QUALIFICATIONS = ["SSCE", "OND", "NCE", "HND", "B.Sc", "B.Eng", "B.A.", "M.Sc / MBA", "Other"]


def _django_errors(fn, *args):
    try:
        return fn(*args)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages))


class ApplicationCreateSerializer(serializers.Serializer):
    """
    The application form (multipart), submitted by a signed-in account. Field
    names match the form inputs. A parent fills in the child's details; the
    child's email is optional. Self-applicants apply with their account email.
    """

    # Personal
    firstName = serializers.CharField(max_length=60)
    middleName = serializers.CharField(max_length=60, required=False, allow_blank=True, default="")
    lastName = serializers.CharField(max_length=60)
    gender = serializers.ChoiceField(Application.Gender.choices)
    dob = serializers.DateField()
    phone = serializers.CharField(max_length=30)
    email = serializers.EmailField(max_length=254, required=False, allow_blank=True, default="")
    address = serializers.CharField(max_length=300)
    state = serializers.ChoiceField(STATES)
    lga = serializers.CharField(max_length=80)

    # Education
    qualification = serializers.ChoiceField(QUALIFICATIONS)
    institution = serializers.CharField(max_length=200)
    gradYear = serializers.IntegerField(min_value=1970)
    waecStatus = serializers.ChoiceField(Application.WaecStatus.choices)
    waecYear = serializers.IntegerField(min_value=1990, required=False, allow_null=True)
    numAs = serializers.IntegerField(min_value=0, max_value=9, required=False, allow_null=True)
    resultFile = serializers.FileField(required=False, allow_null=True)

    # Programme
    programmeId = serializers.SlugRelatedField(
        slug_field="slug", queryset=Programme.objects.filter(status=Programme.Status.ACTIVE),
        error_messages={"does_not_exist": "Please select a programme from the list."},
    )
    schedule = serializers.CharField(max_length=80)
    awardRequest = serializers.ChoiceField(["none", *AwardRequest.Type.values], default="none")
    declare = serializers.BooleanField()

    def validate_phone(self, value):
        return _django_errors(normalize_ng_phone, value)

    def validate_email(self, value):
        return value.strip().lower()

    def validate_dob(self, value):
        now = today()
        if value < date(1950, 1, 1) or value > now.replace(year=now.year - 12):
            raise serializers.ValidationError("Enter a valid date of birth (you must be at least 12 years old).")
        return value

    def validate_gradYear(self, value):
        if value > today().year:
            raise serializers.ValidationError("Graduation year can't be in the future.")
        return value

    def validate_resultFile(self, value):
        if value:
            _django_errors(validate_document, value)
        return value

    def validate_declare(self, value):
        if not value:
            raise serializers.ValidationError("Please confirm that your information is accurate.")
        return value

    def validate(self, attrs):
        errors = {}
        if attrs["waecStatus"] == Application.WaecStatus.AVAILABLE:
            if attrs.get("waecYear") is None:
                errors["waecYear"] = "Exam year is required."
            elif attrs["waecYear"] > today().year:
                errors["waecYear"] = "Exam year can't be in the future."
            if attrs.get("numAs") is None:
                errors["numAs"] = "Number of A's is required."
        else:
            attrs["waecYear"], attrs["numAs"], attrs["resultFile"] = None, 0, None

        if attrs["schedule"] not in attrs["programmeId"].schedules:
            errors["schedule"] = "Choose one of the schedules offered for this programme."

        if errors:
            raise serializers.ValidationError(errors)
        return attrs


class ApplicationSerializer(serializers.ModelSerializer):
    """An application as its owner (or staff) sees it."""

    id = serializers.CharField(source="number")
    name = serializers.CharField(source="full_name")
    firstName = serializers.CharField(source="first_name")
    lastName = serializers.CharField(source="last_name")
    programmeId = serializers.CharField(source="programme.slug")
    programmeName = serializers.CharField(source="programme.name")
    intake = serializers.CharField(source="cohort.name")
    cohortStart = serializers.DateField(source="cohort.start_date")
    discountType = serializers.CharField(source="discount_type")
    discountPct = serializers.IntegerField(source="discount_pct")
    discountAmount = serializers.IntegerField(source="discount_amount")
    amountPayable = serializers.IntegerField(source="amount_payable")
    paymentStatus = serializers.CharField(source="payment_status")
    createdAt = serializers.DateTimeField(source="created_at")
    paidAt = serializers.DateTimeField(source="paid_at")
    middleName = serializers.CharField(source="middle_name")
    waecStatus = serializers.CharField(source="waec_status")
    waecYear = serializers.IntegerField(source="waec_year")
    numAs = serializers.IntegerField(source="num_as")
    gradYear = serializers.IntegerField(source="grad_year")
    hasResultFile = serializers.SerializerMethodField()
    txRef = serializers.SerializerMethodField()
    applicationFee = serializers.IntegerField(source="application_fee")
    applicationFeePaidAt = serializers.DateTimeField(source="application_fee_paid_at")
    # The application-fee part of amountPayable (0 if it was paid separately earlier and credited).
    applicationFeeDue = serializers.SerializerMethodField()
    studentId = serializers.SerializerMethodField()
    awardRequest = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            "id", "name", "firstName", "middleName", "lastName", "gender", "dob", "email", "phone", "address", "state",
            "lga", "qualification", "institution", "gradYear", "waecStatus", "waecYear", "numAs", "hasResultFile",
            "programmeId", "programmeName", "intake", "cohortStart", "schedule", "applicationFee", "applicationFeePaidAt",
            "applicationFeeDue",
            "fee", "discountType", "discountPct",
            "discountAmount", "amountPayable", "status", "paymentStatus", "txRef", "createdAt", "paidAt",
            "studentId", "awardRequest", "history",
        ]

    def get_hasResultFile(self, obj):
        return bool(obj.waec_file)

    def get_applicationFeeDue(self, obj):
        return max(0, obj.amount_payable - (obj.fee - obj.discount_amount))

    def get_txRef(self, obj):
        """Reference of the programme-fee payment (the main receipt)."""
        paid = obj.payments.filter(kind="charge", purpose="programme_fee", status="SUCCESS").order_by("verified_at").first()
        return paid.reference if paid else None

    def get_studentId(self, obj):
        enrollment = getattr(obj, "enrollment", None)
        return enrollment.student.student_no if enrollment else None

    def get_awardRequest(self, obj):
        award = getattr(obj, "award_request", None)
        if award is None:
            return None
        return {"type": award.type, "status": award.status, "requestedPct": award.requested_pct,
                "awardedPct": award.awarded_pct, "note": award.note}

    def get_history(self, obj):
        return [{"at": e.at, "text": e.text, "ok": e.ok} for e in obj.events.all()]
