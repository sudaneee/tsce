"""
Rate limits for the server-rendered forms, sharing the scopes and rates of the
API (REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]) and its cache.
"""
import time

from django.conf import settings
from django.core.cache import cache

PERIODS = {"s": 1, "sec": 1, "m": 60, "min": 60, "h": 3600, "hour": 3600, "d": 86400, "day": 86400}


def client_ip(request) -> str:
    proxies = settings.REST_FRAMEWORK.get("NUM_PROXIES") or 0
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if proxies and xff:
        hops = [a.strip() for a in xff.split(",")]
        return hops[-min(proxies, len(hops))]
    return request.META.get("REMOTE_ADDR", "")


def allow(request, scope: str) -> bool:
    """Counts this request against `scope`; False once the limit is reached."""
    rate = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].get(scope)
    if not rate:
        return True
    count, period = rate.split("/")
    limit, window = int(count), PERIODS[period]
    who = f"u{request.user.pk}" if request.user.is_authenticated else client_ip(request)
    key = f"web-throttle:{scope}:{who}"
    now = time.time()
    hits = [t for t in cache.get(key, []) if t > now - window]
    if len(hits) >= limit:
        return False
    hits.append(now)
    cache.set(key, hits, window)
    return True
