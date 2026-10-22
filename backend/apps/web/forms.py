"""
Forms for the server-rendered pages. Field names match the old API (camelCase)
so the validated data feeds straight into admissions.services.create_application().
"""
from datetime import date

from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.admissions.discounts import today
from apps.admissions.models import Application
from apps.admissions.choices import QUALIFICATIONS, STATES
from apps.core.validators import normalize_ng_phone, validate_document
from apps.programmes.models import Programme


def _choices(values, blank="Select"):
    return [("", blank), *[(v, v) for v in values]]


class StyledForm(forms.Form):
    """Adds the site's input classes so templates can render fields generically."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, forms.Select):
                w.attrs.setdefault("class", "select")
            elif not isinstance(w, (forms.CheckboxInput, forms.RadioSelect, forms.ClearableFileInput, forms.FileInput)):
                w.attrs.setdefault("class", "input")


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------
class LoginForm(StyledForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"id": "loginEmail", "autocomplete": "username"}))
    password = forms.CharField(strip=False, widget=forms.PasswordInput(attrs={"id": "loginPassword", "autocomplete": "current-password"}))
    remember = forms.BooleanField(required=False, initial=True, widget=forms.CheckboxInput(attrs={"id": "loginRemember"}))


class RegisterForm(StyledForm):
    accountType = forms.ChoiceField(choices=[("student", "Myself"), ("parent", "My child / ward")], initial="student",
                                    widget=forms.RadioSelect)
    fullName = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"id": "rName", "autocomplete": "name"}))
    email = forms.EmailField(max_length=254, widget=forms.EmailInput(attrs={"id": "rEmail", "autocomplete": "email"}))
    phone = forms.CharField(max_length=30, widget=forms.TextInput(attrs={"id": "rPhone", "autocomplete": "tel", "placeholder": "0803 123 4567"}))
    password = forms.CharField(strip=False, max_length=128, widget=forms.PasswordInput(attrs={"id": "rPw", "autocomplete": "new-password"}))
    password2 = forms.CharField(strip=False, label="Confirm password", widget=forms.PasswordInput(attrs={"id": "rPw2", "autocomplete": "new-password"}))

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_phone(self):
        return normalize_ng_phone(self.cleaned_data["phone"])

    def clean(self):
        d = super().clean()
        if d.get("password") and d.get("password2") is not None and d["password"] != d.get("password2"):
            self.add_error("password2", "The passwords don't match.")
        if d.get("password") and d.get("email"):
            try:
                password_validation.validate_password(d["password"], User(email=d["email"], full_name=d.get("fullName", "")))
            except ValidationError as exc:
                self.add_error("password", exc)
        return d


class EmailForm(StyledForm):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"autocomplete": "email"}))


# ---------------------------------------------------------------------------
# Application wizard — one form per step; all are re-checked on submit.
# ---------------------------------------------------------------------------
class PersonalForm(StyledForm):
    firstName = forms.CharField(max_length=60, label="First name", widget=forms.TextInput(attrs={"id": "a_first", "autocomplete": "given-name"}))
    middleName = forms.CharField(max_length=60, required=False, label="Middle name", widget=forms.TextInput(attrs={"id": "a_middle", "autocomplete": "additional-name"}))
    lastName = forms.CharField(max_length=60, label="Last name", widget=forms.TextInput(attrs={"id": "a_last", "autocomplete": "family-name"}))
    gender = forms.ChoiceField(choices=_choices(Application.Gender.values), widget=forms.Select(attrs={"id": "a_gender"}))
    dob = forms.DateField(label="Date of birth", widget=forms.DateInput(attrs={"id": "a_dob", "type": "date", "min": "1950-01-01"}, format="%Y-%m-%d"))
    phone = forms.CharField(max_length=30, widget=forms.TextInput(attrs={"id": "a_phone", "autocomplete": "tel", "placeholder": "0803 123 4567"}))
    email = forms.EmailField(max_length=254, required=False, label="Applicant's email (optional)",
                             widget=forms.EmailInput(attrs={"id": "a_email", "autocomplete": "email"}))
    state = forms.ChoiceField(choices=_choices(STATES), widget=forms.Select(attrs={"id": "a_state"}))
    address = forms.CharField(max_length=300, label="Residential address", widget=forms.TextInput(attrs={"id": "a_address", "autocomplete": "street-address"}))
    lga = forms.CharField(max_length=80, label="LGA", widget=forms.TextInput(attrs={"id": "a_lga"}))

    def __init__(self, *args, parent=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not parent:  # self-applicants always apply with their account email
            del self.fields["email"]

    def clean_phone(self):
        return normalize_ng_phone(self.cleaned_data["phone"])

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()

    def clean_dob(self):
        value, now = self.cleaned_data["dob"], today()
        if value < date(1950, 1, 1) or value > now.replace(year=now.year - 12):
            raise ValidationError("Enter a valid date of birth (the applicant must be at least 12 years old).")
        return value


class EducationForm(StyledForm):
    qualification = forms.ChoiceField(label="Highest qualification", choices=_choices(QUALIFICATIONS), widget=forms.Select(attrs={"id": "a_qual"}))
    gradYear = forms.IntegerField(label="Graduation year", min_value=1970, widget=forms.NumberInput(attrs={"id": "a_grad", "placeholder": "e.g. 2023"}))
    institution = forms.CharField(max_length=200, widget=forms.TextInput(attrs={"id": "a_inst", "placeholder": "e.g. Ahmadu Bello University, Zaria"}))
    waecStatus = forms.ChoiceField(label="WAEC / NECO status", choices=_choices(Application.WaecStatus.values), widget=forms.Select(attrs={"id": "a_waec"}))
    waecYear = forms.IntegerField(label="Exam year", min_value=1990, required=False, widget=forms.NumberInput(attrs={"id": "a_waecYear", "placeholder": "e.g. 2022"}))
    numAs = forms.IntegerField(label="Number of A's", min_value=0, max_value=9, required=False, widget=forms.NumberInput(attrs={"id": "a_numAs", "placeholder": "0–9"}))
    resultFile = forms.FileField(label="Upload result", required=False, widget=forms.FileInput(attrs={"id": "a_file", "accept": ".pdf,.jpg,.jpeg,.png"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        year = today().year
        self.fields["gradYear"].widget.attrs["max"] = year
        self.fields["waecYear"].widget.attrs["max"] = year

    def clean_gradYear(self):
        value = self.cleaned_data["gradYear"]
        if value > today().year:
            raise ValidationError("Graduation year can't be in the future.")
        return value

    def clean_resultFile(self):
        f = self.cleaned_data.get("resultFile")
        if f:
            validate_document(f)
        return f

    def clean(self):
        d = super().clean()
        if d.get("waecStatus") == Application.WaecStatus.AVAILABLE:
            if d.get("waecYear") is None:
                self.add_error("waecYear", "Exam year is required.")
            elif d["waecYear"] > today().year:
                self.add_error("waecYear", "Exam year can't be in the future.")
            if d.get("numAs") is None:
                self.add_error("numAs", "Number of A's is required.")
        elif d.get("waecStatus"):
            d["waecYear"], d["numAs"] = None, 0
        return d


def active_programmes():
    return Programme.objects.filter(status=Programme.Status.ACTIVE).order_by("name")


class ProgrammeForm(StyledForm):
    programmeId = forms.ModelChoiceField(queryset=Programme.objects.none(), to_field_name="slug", label="Programme",
                                         widget=forms.RadioSelect,
                                         error_messages={"invalid_choice": "Please select a programme from the list.",
                                                         "required": "Please select a programme."})
    schedule = forms.ChoiceField(label="Preferred schedule", widget=forms.Select(attrs={"id": "a_schedule"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        programmes = active_programmes()
        self.fields["programmeId"].queryset = programmes
        schedules = []
        for p in programmes:
            schedules += [s for s in p.schedules if s not in schedules]
        self.fields["schedule"].choices = _choices(schedules)

    def clean(self):
        d = super().clean()
        if d.get("programmeId") and d.get("schedule") and d["schedule"] not in d["programmeId"].schedules:
            self.add_error("schedule", "Choose one of the schedules offered for this programme.")
        return d


class ReviewForm(StyledForm):
    awardRequest = forms.ChoiceField(choices=[("none", "No award"), ("excellence", "Excellence Award")], initial="none",
                                     widget=forms.RadioSelect)
    declare = forms.BooleanField(error_messages={"required": "Please confirm that the information is accurate."},
                                 widget=forms.CheckboxInput(attrs={"id": "a_declare"}))


class PayForm(forms.Form):
    plan = forms.ChoiceField(choices=[("full", "Pay in full"), ("half", "Pay 50% now")], initial="full", required=False)
    # The amounts the payer saw for each option, to catch a price change before charging.
    amount_full = forms.IntegerField(min_value=0)
    amount_half = forms.IntegerField(min_value=0, required=False)

    def shown(self, plan: str):
        return self.cleaned_data["amount_half"] if plan == "half" else self.cleaned_data["amount_full"]


# ---------------------------------------------------------------------------
# Staff portal
# ---------------------------------------------------------------------------
class NoteForm(StyledForm):
    note = forms.CharField(max_length=300, required=False, widget=forms.Textarea(attrs={"rows": 3, "class": "textarea"}))


class RefundForm(StyledForm):
    transferRef = forms.CharField(max_length=100, label="Bank transfer reference")
    note = forms.CharField(max_length=300, required=False, widget=forms.TextInput(attrs={"placeholder": "e.g. Paid twice from two tabs"}))


class StaffMemberForm(StyledForm):
    ACCESS = [("none", "No login (e.g. instructor)"), ("staff", "Staff portal"), ("admin", "Admin (staff + settings)")]

    fullName = forms.CharField(max_length=150, label="Full name", widget=forms.TextInput(attrs={"id": "st_n"}))
    title = forms.CharField(max_length=120, label="Job title", widget=forms.TextInput(attrs={"id": "st_t", "placeholder": "e.g. Instructor — Networking"}))
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"id": "st_e"}))
    phone = forms.CharField(max_length=30, required=False, widget=forms.TextInput(attrs={"id": "st_p"}))
    department = forms.ChoiceField(choices=[], widget=forms.Select(attrs={"id": "st_d"}))
    access = forms.ChoiceField(choices=ACCESS, label="Portal access", initial="staff", widget=forms.Select(attrs={"id": "st_a"}))
    status = forms.ChoiceField(choices=[], required=False, widget=forms.Select(attrs={"id": "st_s"}))

    def __init__(self, *args, editing=None, is_self=False, **kwargs):
        from apps.accounts.models import StaffProfile

        super().__init__(*args, **kwargs)
        self.fields["department"].choices = StaffProfile.Department.choices
        self.fields["status"].choices = StaffProfile.Status.choices
        if editing is None:
            del self.fields["status"]
        elif editing.user_id:
            self.fields["email"].disabled = True  # the sign-in email isn't changed here
        if is_self:
            self.fields["access"].disabled = True
            self.fields["status"].disabled = True

    def clean_email(self):
        return (self.cleaned_data.get("email") or "").strip().lower()

    def clean_phone(self):
        value = self.cleaned_data.get("phone") or ""
        return normalize_ng_phone(value) if value else ""


class InstitutionForm(StyledForm):
    name = forms.CharField(max_length=200)
    short = forms.CharField(max_length=20, label="Short name")
    city = forms.CharField(max_length=120, required=False)
    address = forms.CharField(max_length=300)
    phones = forms.CharField(max_length=200, label="Phone numbers (comma-separated)")
    email = forms.EmailField(required=False)
    website = forms.CharField(max_length=120, required=False)
    directorName = forms.CharField(max_length=120, required=False, label="Director's name (signs certificates)")
    directorTitle = forms.CharField(max_length=120, required=False, label="Director's title")

    def clean_phones(self):
        phones = [x.strip() for x in self.cleaned_data["phones"].split(",") if x.strip()]
        if not phones or len(phones) > 6:
            raise ValidationError("Enter between one and six phone numbers, separated by commas.")
        return phones


class AdmissionsForm(StyledForm):
    intake = forms.CharField(max_length=80, label="Current intake name")
    opens = forms.DateField(required=False, label="Applications open", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    closes = forms.DateField(required=False, label="Applications close", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    cohortDate = forms.DateField(label="Classes start", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    earlyBirdDeadline = forms.DateField(required=False, label="Early bird: programme fee paid before",
                                        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    applicationFee = forms.IntegerField(min_value=0, max_value=1_000_000, label="Application fee (₦, added to the programme fee)")
    acceptingApplications = forms.BooleanField(required=False)
    allowInstallments = forms.BooleanField(required=False)

    def clean(self):
        d = super().clean()
        if d.get("opens") and d.get("closes") and d["opens"] > d["closes"]:
            self.add_error("closes", "The closing date must be after the opening date.")
        if d.get("closes") and d.get("cohortDate") and d["closes"] > d["cohortDate"]:
            self.add_error("closes", "Applications should close on or before the cohort start date.")
        return d


class DiscountsForm(StyledForm):
    earlyBirdPct = forms.IntegerField(min_value=0, max_value=100, label="Early bird (%)")
    excellencePct = forms.IntegerField(min_value=0, max_value=100, label="Excellence Award (%)")
    excellenceMinYear = forms.IntegerField(min_value=2000, max_value=2100, label="Excellence: WAEC/NECO from year")
    excellenceMinAs = forms.IntegerField(min_value=1, max_value=9, label="Excellence: minimum A's")


class NotificationSettingsForm(StyledForm):
    emailNotifications = forms.BooleanField(required=False)
    staffPaymentAlerts = forms.BooleanField(required=False)
    staffApplicationAlerts = forms.BooleanField(required=False)


class IntakeForm(StyledForm):
    intake = forms.CharField(max_length=80, label="Intake name", widget=forms.TextInput(attrs={"placeholder": "e.g. January 2027 Cohort"}))
    opens = forms.DateField(required=False, label="Applications open", widget=forms.DateInput(attrs={"type": "date"}))
    closes = forms.DateField(required=False, label="Applications close", widget=forms.DateInput(attrs={"type": "date"}))
    cohortDate = forms.DateField(label="Classes start", widget=forms.DateInput(attrs={"type": "date"}))
    earlyBirdDeadline = forms.DateField(required=False, label="Early bird: paid before", widget=forms.DateInput(attrs={"type": "date"}))

    def clean_intake(self):
        from apps.programmes.models import Cohort

        name = self.cleaned_data["intake"].strip()
        if Cohort.objects.filter(name__iexact=name).exists():
            raise ValidationError("An intake with that name already exists.")
        return name


# ---------------------------------------------------------------------------
# Public site
# ---------------------------------------------------------------------------
class EnquiryForm(StyledForm):
    name = forms.CharField(max_length=120, label="Full name", widget=forms.TextInput(attrs={"id": "c_name", "autocomplete": "name"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"id": "c_email", "autocomplete": "email"}))
    phone = forms.CharField(max_length=30, widget=forms.TextInput(attrs={"id": "c_phone", "autocomplete": "tel", "placeholder": "0803 123 4567"}))
    programme = forms.ChoiceField(required=False, label="Programme of interest", widget=forms.Select(attrs={"id": "c_prog"}))
    subject = forms.CharField(max_length=150, required=False, widget=forms.TextInput(attrs={"id": "c_subject"}))
    message = forms.CharField(min_length=10, widget=forms.Textarea(attrs={"id": "c_msg", "class": "textarea"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["programme"].choices = [("", "General enquiry"), *[(p.name, p.name) for p in active_programmes()]]

    def clean_phone(self):
        return normalize_ng_phone(self.cleaned_data["phone"])
