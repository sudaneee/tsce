"""
Template context shared by every server-rendered page: school details for the
header and footer, the admissions calendar for the announcement bar, and the
asset version that busts browser/Cloudflare caches on each release.
"""
import json
from functools import lru_cache

from django.conf import settings

from apps.admissions.discounts import admissions_state, early_bird_open
from apps.core.models import SiteSettings

CATALOGUE = settings.BASE_DIR / "apps" / "programmes" / "data" / "catalogue.json"

NAV = [  # (href, text, icon, key matched against the page's active_nav)
    ("/index.html", "Home", "fa-house", "home"), ("/pages/about.html", "About", "fa-building-columns", "about"),
    ("/pages/programmes.html", "Programmes", "fa-layer-group", "programmes"),
    ("/pages/admissions.html", "Admissions", "fa-door-open", "admissions"),
    ("/pages/admissions.html#scholarships", "Scholarships", "fa-award", ""), ("/index.html#why", "Why TSCE", "fa-star", ""),
    ("/pages/news.html", "News & Events", "fa-newspaper", "news"), ("/pages/contact.html", "Contact", "fa-phone", "contact"),
]
SOCIALS = [("fa-facebook-f", "Facebook"), ("fa-instagram", "Instagram"), ("fa-x-twitter", "X (Twitter)"),
           ("fa-linkedin-in", "LinkedIn"), ("fa-youtube", "YouTube"), ("fa-tiktok", "TikTok")]


@lru_cache(maxsize=1)
def flyer() -> dict:
    return json.loads(CATALOGUE.read_text(encoding="utf-8"))["flyer"]


@lru_cache(maxsize=1)
def asset_version() -> str:
    """Changes whenever a stylesheet or script changes (they are deployed together)."""
    try:
        files = [*settings.FRONTEND_DIR.glob("css/*.css"), *settings.FRONTEND_DIR.glob("js/site.js")]
        return str(int(max((f.stat().st_mtime for f in files), default=0)))
    except OSError:  # never let a cache-buster take a page down
        return "1"


def home_for(user) -> str:
    """Where a signed-in account belongs."""
    if user.role in ("staff", "admin"):
        return "/staff/"
    return "/my-applications/"


def _countdown(cohort) -> str:
    """'5d 3h to kick-off' for the announcement bar (site.js keeps it ticking)."""
    from datetime import datetime

    from django.utils import timezone

    if cohort is None:
        return ""
    start = timezone.make_aware(datetime.combine(cohort.start_date, datetime.min.time().replace(hour=8)))
    secs = (start - timezone.now()).total_seconds()
    if secs <= 0:
        return "Classes are in session"
    return f"{int(secs // 86400)}d {int(secs // 3600) % 24}h to kick-off"


def site(request):
    s = SiteSettings.load()
    cohort = s.current_cohort
    user = request.user
    return {
        "site": s,
        "flyer": flyer(),
        "cohort": cohort,
        "admissions": admissions_state(s),
        "early_bird": early_bird_open(cohort),
        "nav": NAV,
        "socials": SOCIALS,
        "asset_v": asset_version(),
        "countdown": _countdown(cohort),
        "home_url": home_for(user) if user.is_authenticated else "",
        "first_name": user.full_name.split(" ")[0] if user.is_authenticated else "",
    }
