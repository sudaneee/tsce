"""
The 5-step application, rendered and validated on the server:

    1 Personal   2 Education   3 Programme   4 Review (fees, award, declaration)   5 Admission

Steps 1–3 are kept in the session as a draft; step 4 re-checks everything and
calls admissions.services.create_application(); step 5 shows the outcome.
"""
from django.conf import settings as dj_settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.accounts.models import User
from apps.admissions import services
from apps.admissions.discounts import admissions_state, early_bird_open, excellence_eligible, first_installment, quote, seats_taken
from apps.admissions.models import Application, waec_upload_path
from apps.core.exceptions import ServiceError
from apps.core.models import SiteSettings
from apps.core.storage import private_storage

from ..presenters import pay_options
from ..forms import EducationForm, PersonalForm, ProgrammeForm, ReviewForm, active_programmes
from ..throttle import allow
from .common import applicant_required, error_code, error_text

DRAFT = "apply_draft"
STEPS = [
    ("Personal", "Your details", "Personal information", "Tell us about the applicant. Fields marked * are required."),
    ("Education", "Background", "Educational background", "Highest qualification and WAEC/NECO status."),
    ("Programme", "Course & schedule", "Programme selection", "Choose the programme and preferred schedule."),
    ("Review", "Fees & discounts", "Review, fees & discounts", "Check the details, choose whether to request the Excellence Award and see the fees."),
    ("Admission", "Then pay the programme fee", "Admission", ""),
]
FORMS = {1: PersonalForm, 2: EducationForm, 3: ProgrammeForm}
# Where each create_application() error field is edited.
FIELD_STEP = {"programmeId": 3, "schedule": 3, "awardRequest": 4}


def _draft(request) -> dict:
    return request.session.get(DRAFT) or {"done": []}


def _save_draft(request, draft):
    request.session[DRAFT] = draft
    request.session.modified = True


def _is_parent(user) -> bool:
    return user.role == User.Role.PARENT


def _form(step, user, data=None, files=None, initial=None):
    kwargs = {"parent": _is_parent(user)} if step == 1 else {}
    return FORMS[step](data, files, initial=initial, **kwargs)


def _serialise(cleaned: dict) -> dict:
    out = {}
    for k, v in cleaned.items():
        if k == "resultFile":
            continue
        if hasattr(v, "slug"):
            v = v.slug
        elif hasattr(v, "isoformat"):
            v = v.isoformat()
        out[k] = "" if v is None else str(v)
    return out


def _wizard_ctx(step, **extra):
    return {"steps": [{"n": i + 1, "title": t, "sub": s, "state": "done" if i + 1 < step else "active" if i + 1 == step else ""}
                      for i, (t, s, _, _) in enumerate(STEPS)],
            "step": step, "title": STEPS[step - 1][2], "subtitle": STEPS[step - 1][3],
            "progress": round(step / (len(STEPS) + 1) * 100), **extra}


def _gate(request):
    """Why this account can't apply right now (rendered instead of the wizard), or None."""
    user = request.user
    state = admissions_state(SiteSettings.load())
    if not state.open:
        return render(request, "web/apply/closed.html", {"message": state.message})
    if user.needs_email_verification:
        return render(request, "web/apply/gate.html", {"unverified": True})
    return None


def apply_start(request):
    if not request.user.is_authenticated:
        return render(request, "web/apply/gate.html", {"programme": request.GET.get("programme", "")})
    if request.user.is_portal_staff:
        return render(request, "web/apply/gate.html", {"staff": True})
    if request.GET.get("new"):
        request.session.pop(DRAFT, None)
    if request.GET.get("programme"):  # "Apply" from a programme page pre-selects it
        draft = _draft(request)
        data = draft.setdefault("data", {})
        data["3"] = {**data.get("3", {}), "programmeId": request.GET["programme"]}
        _save_draft(request, draft)
    return redirect("web:apply-step", step=1)


@applicant_required
def apply_step(request, step):
    if step not in (1, 2, 3, 4):
        return redirect("web:apply-step", step=1)
    gate = _gate(request)
    if gate:
        return gate
    draft = _draft(request)
    first_missing = next((s for s in (1, 2, 3) if s not in draft["done"]), 4)
    if step > first_missing:
        return redirect("web:apply-step", step=first_missing)
    if step == 4:
        return _review(request, draft)

    saved = draft.get("data", {}).get(str(step), {})
    if request.method == "POST":
        if request.POST.get("nav") == "back":
            return redirect("web:apply-step", step=max(1, step - 1))
        form = _form(step, request.user, request.POST, request.FILES)
        if form.is_valid():
            data = _serialise(form.cleaned_data)
            if step == 2:
                data.update(_store_upload(form.cleaned_data.get("resultFile"), saved))
            draft.setdefault("data", {})[str(step)] = data
            if step not in draft["done"]:
                draft["done"].append(step)
            _save_draft(request, draft)
            return redirect("web:apply-step", step=step + 1)
    else:
        form = _form(step, request.user, initial=saved or _prefill(step, request.user))

    ctx = _wizard_ctx(step, form=form, parent=_is_parent(request.user), saved=saved)
    if step == 3:
        ctx["programmes"] = _programme_cards(form, saved)
    return render(request, "web/apply/wizard.html", ctx)


def _prefill(step, user) -> dict:
    """Step 1 starts with what the account already knows (a parent's own name isn't the child's)."""
    if step != 1:
        return {}
    data = {"phone": user.phone}
    if not _is_parent(user):
        names = user.full_name.split()
        if len(names) >= 2:
            data.update(firstName=names[0], lastName=names[-1], middleName=" ".join(names[1:-1]))
    return data


def _store_upload(upload, saved) -> dict:
    """Keeps the WAEC result in private storage until the application is created."""
    if upload:
        name = private_storage().save(waec_upload_path(None, upload.name), upload)
        return {"resultFileName": name, "resultFileLabel": upload.name}
    return {k: saved[k] for k in ("resultFileName", "resultFileLabel") if k in saved}


def _programme_cards(form, saved):
    cohort = SiteSettings.load().current_cohort
    taken = seats_taken(cohort)
    chosen = form["programmeId"].value() or saved.get("programmeId")
    cards = []
    for p in active_programmes():
        left = max(0, p.capacity - taken.get(p.pk, 0))
        cards.append({"p": p, "left": left, "full": left == 0, "checked": chosen == p.slug})
    return cards


def _all_data(request, draft):
    """Re-validates steps 1–3 from the draft. Returns (data, first step with an error)."""
    data = {}
    for step in (1, 2, 3):
        form = _form(step, request.user, draft.get("data", {}).get(str(step), {}))
        if not form.is_valid():
            return None, step
        data.update(form.cleaned_data)
    data.pop("resultFile", None)
    data.setdefault("email", "")
    data["middleName"] = data.get("middleName") or ""
    name = draft["data"]["2"].get("resultFileName")
    data["resultFile"] = name if (name and data["waecStatus"] == Application.WaecStatus.AVAILABLE) else None
    return data, None


def _fee_preview(data, settings):
    programme, cohort = data["programmeId"], settings.current_cohort
    q = quote(programme, cohort, settings)
    app_fee = settings.application_fee
    total = q.amount_payable + app_fee
    probe = Application(fee=q.fee, discount_amount=q.discount_amount, amount_payable=total)
    return {"fee": q.fee, "discount": q.discount_amount, "pct": q.discount_pct, "app_fee": app_fee,
            "charge": dj_settings.ZAINPAY["PAYER_CHARGE"], "total": total,
            "half": first_installment(probe) if settings.allow_installments else None}


def _review(request, draft):
    data, broken = _all_data(request, draft)
    if broken:
        messages.warning(request, "Please check this step again.")
        return redirect("web:apply-step", step=broken)
    settings = SiteSettings.load()
    eligible = excellence_eligible(settings, data["waecStatus"], data["waecYear"], data["numAs"])
    form = ReviewForm(request.POST or None, initial={"awardRequest": draft.get("award", "none")})
    error = duplicate = None

    if request.method == "POST":
        if request.POST.get("nav") == "back":
            return redirect("web:apply-step", step=3)
        if form.is_valid():
            draft["award"] = form.cleaned_data["awardRequest"]
            _save_draft(request, draft)
            if not allow(request, "apply"):
                error = "Too many applications from this connection. Please try again later."
            else:
                try:
                    app = services.create_application({**data, **form.cleaned_data}, request.user)
                except ServiceError as exc:
                    if error_code(exc) == "duplicate_application":
                        duplicate = exc.extra.get("applicationId")
                    target = FIELD_STEP.get(exc.field or "")
                    if target and target < 4:
                        messages.error(request, error_text(exc))
                        return redirect("web:apply-step", step=target)
                    error = error_text(exc)
                else:
                    request.session.pop(DRAFT, None)
                    return redirect("web:apply-done", number=app.number)

    eb_open = early_bird_open(settings.current_cohort)
    ctx = _wizard_ctx(4, form=form, d=data, fees=_fee_preview(data, settings), eligible=eligible,
                      early_bird=eb_open, settings=settings, parent=_is_parent(request.user),
                      account_email=request.user.email, error=error, duplicate=duplicate,
                      file_label=draft["data"]["2"].get("resultFileLabel", ""))
    return render(request, "web/apply/wizard.html", ctx)


@applicant_required
def apply_done(request, number):
    """Step 5: the outcome — admitted (pay now) or awaiting award verification."""
    app = get_object_or_404(Application.objects.select_related("programme", "cohort"), number=number, user=request.user)
    return render(request, "web/apply/wizard.html",
                  _wizard_ctx(5, app=app, opts=pay_options(app), pay_url=reverse("web:pay", kwargs={"number": app.number})))
