"""
The public website, rendered by Django at its usual addresses (/, /index.html,
/pages/*.html). Programme data, seats, fees, discounts and dates come from the
database and Settings; the browser only animates.
"""
from django.shortcuts import render

from apps.academics.models import Certificate
from apps.admissions.discounts import early_bird_open, seats_taken, today
from apps.comms.models import Announcement, Enquiry, Notification
from apps.comms.services import notify_staff
from apps.core.models import SiteSettings

from ..forms import EnquiryForm, active_programmes
from ..throttle import allow

FEATURED = ["fullstack", "cyber-fund", "data-ai", "network", "digital-marketing", "cisco-cloud"]
GRADIENTS = ["linear-gradient(135deg,#1846D6,#06C8E0)", "linear-gradient(135deg,#0B1D55,#1846D6)",
             "linear-gradient(135deg,#F5B400,#F97316)", "linear-gradient(135deg,#12A150,#0EA5E9)",
             "linear-gradient(135deg,#7C3AED,#1846D6)"]
TAG_ICON = {"Admissions": "fa-door-open", "Event": "fa-calendar-days", "Events": "fa-calendar-days", "Academics": "fa-book-open",
            "Payments": "fa-naira-sign", "Scholarship": "fa-award", "General": "fa-bullhorn"}


def _programmes(settings, cohort):
    """Active programmes with seats left, curriculum weeks and the early-bird price."""
    taken = seats_taken(cohort)
    eb = settings.early_bird_pct if early_bird_open(cohort) else 0
    out = []
    for p in active_programmes().prefetch_related("modules"):
        modules = list(p.modules.all())
        enrolled = taken.get(p.pk, 0)
        available = max(0, p.capacity - enrolled)
        n = max(1, len(modules))
        p.card = {
            "modules": [(m.title, max(1, round((i + 1) * p.weeks / n))) for i, m in enumerate(modules)],
            "enrolled": enrolled, "available": available,
            "pct": round(enrolled / p.capacity * 100) if p.capacity else 0,
            "eb_price": p.fee - round(p.fee * eb / 100) if eb else None,      # only while the early bird is open
            "eb_discount": round(p.fee * settings.early_bird_pct / 100),     # for the published fee table
            "eb_listed": p.fee - round(p.fee * settings.early_bird_pct / 100),
            "eb_total": p.fee - round(p.fee * settings.early_bird_pct / 100) + settings.application_fee,
            "excellence_price": p.fee - round(p.fee * settings.excellence_pct / 100),
            "search": " ".join([p.name, p.overview, *[m.title for m in modules]]).lower(),
        }
        out.append(p)
    return out


def _calendar(cohort, settings):
    """Key dates for the timelines (only the ones TSCE has set)."""
    if cohort is None:
        return []
    items = []
    eb = cohort.early_bird_deadline
    if eb:
        items.append({"date": eb, "tone": "gold", "title": "Early-bird deadline",
                      "text": f"Pay before {eb.day} {eb:%B} for {settings.early_bird_pct}% off", "early_bird": True})
    if cohort.enrolment_opens:
        items.append({"date": cohort.enrolment_opens, "tone": "", "title": "Registration opens",
                      "text": "Online applications open"})
    if cohort.enrolment_closes:
        items.append({"date": cohort.enrolment_closes, "tone": "", "title": "Registration closes",
                      "text": "Final day to apply"})
    s = cohort.start_date
    items.append({"date": s, "tone": "green", "title": "Programme commences", "text": f"{s:%A}, {s.day} {s:%B %Y}"})
    return sorted(items, key=lambda i: i["date"])


def _base(settings):
    cohort = settings.current_cohort
    return {"settings": settings, "cohort": cohort, "calendar": _calendar(cohort, settings),
            "eb_open": early_bird_open(cohort), "today": today()}


def home(request):
    s = SiteSettings.load()
    ctx = _base(s)
    progs = {p.slug: p for p in _programmes(s, ctx["cohort"])}
    featured = [progs[slug] for slug in FEATURED if slug in progs]
    fees = sorted(p.fee for p in progs.values())
    return render(request, "web/public/home.html", {**ctx, "featured": featured, "programme_count": len(progs),
                                                    "fee_min": fees[0] if fees else 0, "fee_max": fees[-1] if fees else 0,
                                                    "active_nav": "home"})


def about(request):
    return render(request, "web/public/about.html", {**_base(SiteSettings.load()), "active_nav": "about"})


def programmes(request):
    s = SiteSettings.load()
    ctx = _base(s)
    allp = _programmes(s, ctx["cohort"])
    tracks = sorted({p.track for p in allp})
    track, q, sort = request.GET.get("track") or "All", (request.GET.get("q") or "").strip().lower(), request.GET.get("sort") or ""
    shown = [p for p in allp if (track == "All" or p.track == track) and q in p.card["search"]]
    if sort == "fee-asc":
        shown.sort(key=lambda p: p.fee)
    elif sort == "fee-desc":
        shown.sort(key=lambda p: -p.fee)
    elif sort == "weeks":
        shown.sort(key=lambda p: p.weeks)
    return render(request, "web/public/programmes.html", {**ctx, "programmes": shown, "all_programmes": allp,
                                                          "tracks": ["All", *tracks], "track": track, "q": q, "sort": sort,
                                                          "open_id": request.GET.get("id", ""), "active_nav": "programmes"})


def admissions(request):
    s = SiteSettings.load()
    ctx = _base(s)
    progs = _programmes(s, ctx["cohort"])
    example = next((p for p in progs if p.slug == "fullstack"), progs[0] if progs else None)
    return render(request, "web/public/admissions.html", {**ctx, "programmes": progs, "example": example,
                                                          "active_nav": "admissions"})


def news(request):
    s = SiteSettings.load()
    items = list(Announcement.objects.filter(status=Announcement.Status.PUBLISHED, audience=Announcement.Audience.PUBLIC)
                 .select_related("author")[:30])
    for i, a in enumerate(items):
        a.gradient, a.icon = GRADIENTS[i % len(GRADIENTS)], TAG_ICON.get(a.tag, "fa-bullhorn")
        a.byline = a.author_label or (a.author.full_name if a.author else "TSCE")
    return render(request, "web/public/news.html", {**_base(s), "items": items, "active_nav": "news"})


def contact(request):
    s = SiteSettings.load()
    form = EnquiryForm(request.POST or None)
    sent = error = None
    if request.method == "POST":
        if not allow(request, "public_form"):
            error = "Too many messages from this connection. Please try again later or call us."
        elif form.is_valid():
            enquiry = Enquiry.objects.create(**form.cleaned_data)
            notify_staff("New enquiry", f"{enquiry.name}: {enquiry.subject or enquiry.programme or 'General enquiry'}",
                         Notification.Type.SUPPORT)
            sent = enquiry.name.split()[0]
            form = EnquiryForm()
    return render(request, "web/public/contact.html", {**_base(s), "form": form, "sent": sent, "error": error,
                                                       "active_nav": "contact"})


def verify(request):
    number = (request.GET.get("no") or "").strip()
    result = None
    if number:
        cert = (Certificate.objects.select_related("enrollment__student", "enrollment__programme", "enrollment__cohort")
                .filter(number__iexact=number).first()) if allow(request, "verify") else None
        if cert is None:
            result = {"status": "not_found", "number": number}
        elif cert.status == Certificate.Status.REVOKED:
            result = {"status": "revoked", "number": cert.number}
        else:
            e = cert.enrollment
            result = {"status": "valid", "number": cert.number, "holder": e.student.full_name, "programme": e.programme.name,
                      "cohort": e.cohort.name, "issued_at": cert.issued_at}
    return render(request, "web/public/verify.html", {**_base(SiteSettings.load()), "number": number, "result": result})

