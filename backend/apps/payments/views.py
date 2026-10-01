import hashlib
import hmac
import json
import logging
from html import escape
from urllib.parse import urlencode

from django.conf import settings
from django.db.models import Q, Sum
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.accounts.permissions import IsPortalStaff
from apps.admissions.models import Application
from apps.core.exceptions import ServiceError

from . import services
from apps.core.background import run_in_background

from .gateways import GatewayError
from .models import Payment, WebhookEvent

logger = logging.getLogger(__name__)

# Remembered on the browser session when checkout starts, so the callback can
# recover the payment if Zainpay's redirect ever arrives without ?txnRef=.
# This is the ONLY fallback allowed: never guess "the latest pending payment"
# across the database (that once marked another family's invoice as paid in
# the Glittering project).
SESSION_REF = "pending_payment_ref"


class PaymentSerializer(serializers.ModelSerializer):
    ref = serializers.CharField(source="reference")
    applicationId = serializers.CharField(source="application.number", default=None)
    programmeId = serializers.CharField(source="application.programme.slug", default=None)
    studentId = serializers.SerializerMethodField()
    failureReason = serializers.CharField(source="failure_reason")
    createdAt = serializers.DateTimeField(source="created_at")
    verifiedAt = serializers.DateTimeField(source="verified_at")
    refundedAt = serializers.DateTimeField(source="refunded_at")

    class Meta:
        model = Payment
        fields = ["ref", "kind", "purpose", "applicationId", "programmeId", "studentId", "name", "email", "description", "amount",
                  "fee", "discount", "status", "channel", "gateway", "failureReason", "createdAt", "verifiedAt", "refundedAt"]

    def get_studentId(self, obj):
        # The enrolled person (a parent's child has no user of their own).
        enrollment = getattr(obj.application, "enrollment", None) if obj.application_id else None
        return enrollment.student.student_no if enrollment else None


def _visible_payments(user):
    qs = Payment.objects.select_related("application__programme", "application__enrollment__student")
    if user.is_portal_staff:
        return qs
    return qs.filter(Q(user=user) | Q(application__user=user))


def callback_url(request):
    return settings.ZAINPAY["CALLBACK_URL"] or request.build_absolute_uri("/api/payments/zainpay/callback")


class InitializePaymentView(APIView):
    """POST {applicationId, purpose: application_fee|programme_fee} → {ref, checkoutUrl, amount}."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "payment"

    def post(self, request):
        number = str(request.data.get("applicationId") or "")
        app = Application.objects.filter(number=number, user=request.user).first()
        if app is None:
            raise Http404
        purpose = str(request.data.get("purpose") or Payment.Purpose.APPLICATION_FEE)
        payment = services.start_checkout(app, purpose, callback_url(request))
        request.session[SESSION_REF] = payment.reference
        return Response({"ref": payment.reference, "purpose": payment.purpose, "checkoutUrl": payment.checkout_url,
                         "amount": payment.amount})


class PaymentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, ref):
        return Response(PaymentSerializer(get_object_or_404(_visible_payments(request.user), reference=ref)).data)


class PaymentCheckView(APIView):
    """"Check status": asks the gateway again for a payment that isn't confirmed yet."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "payment"

    def post(self, request, ref):
        payment = get_object_or_404(_visible_payments(request.user), reference=ref)
        try:
            payment = services.process_payment(payment)
        except GatewayError as exc:
            logger.warning("Status check for %s failed: %s", ref, exc)
            raise ServiceError("We couldn't reach the payment provider. Please try again shortly.",
                               "gateway_unavailable", status_code=502)
        return Response(PaymentSerializer(payment).data)


def _frontend_redirect(payment, outcome):
    if payment and payment.status == Payment.Status.SUCCESS:
        return HttpResponseRedirect("/pages/success.html?" + urlencode({"ref": payment.reference}))
    query = {"result": outcome}
    if payment:
        query["ref"] = payment.reference
        if payment.application_id:
            query["app"] = payment.application.number
    return HttpResponseRedirect("/pages/payment.html?" + urlencode(query))


@csrf_exempt
@require_http_methods(["GET", "POST"])
def zainpay_callback(request):
    """
    GET  — the payer's browser returning from checkout (?txnRef=…): verify, then
           send them to the success page or back to the payment page.
    POST — some Zainpay setups post the webhook to the callback URL; handled as one.
    """
    if request.method == "POST":
        return zainpay_webhook(request)

    ref = request.GET.get("txnRef") or request.GET.get("reference") or request.session.get(SESSION_REF)
    payment = Payment.objects.select_related("application").filter(reference=ref).first() if ref else None
    if payment is None:
        return HttpResponseRedirect("/pages/payment.html?" + urlencode({"result": "unknown"}))
    request.session.pop(SESSION_REF, None)
    try:
        payment = services.process_payment(payment)
    except GatewayError as exc:
        logger.error("Callback verify failed for %s: %s", payment.reference, exc)
        return _frontend_redirect(payment, "pending")
    outcome = {"SUCCESS": "success", "FAILED": "failed"}.get(payment.status, "pending")
    return _frontend_redirect(payment, outcome)


def _signature_ok(raw: bytes, received: str) -> bool:
    secret = settings.ZAINPAY["SECRET_KEY"]
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, received or "")


@csrf_exempt
@require_http_methods(["POST"])
def zainpay_webhook(request):
    """
    Server-to-server notification. Stored first (audit), signature checked, and
    then the payment is re-verified with Zainpay's API — the webhook body itself
    is never trusted. Answers 200 so Zainpay stops retrying (400 only for a bad
    signature).
    """
    raw = request.body
    signed = bool(settings.ZAINPAY["SECRET_KEY"])
    received_sig = request.headers.get("Zainpay-Signature", "")
    valid = _signature_ok(raw, received_sig) if signed else False
    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        payload = {"_raw": raw[:2000].decode("utf-8", "replace")}
    if not isinstance(payload, dict):
        payload = {"_raw": payload}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    event_type = str(payload.get("event") or payload.get("event_type") or "")
    ref = str(data.get("txnRef") or payload.get("txnRef") or "")
    event = WebhookEvent.objects.create(
        gateway="zainpay", event_type=event_type[:60], reference=ref[:100], payload=payload,
        headers={"Zainpay-Signature": received_sig}, signature_valid=valid,
    )

    if signed and not valid:
        logger.warning("Zainpay webhook with invalid signature (event %s)", event.pk)
        event.error = "invalid signature"
        event.save(update_fields=["error"])
        return JsonResponse({"status": "error", "reason": "invalid signature"}, status=401)

    if "deposit" not in event_type.lower():
        event.error = f"event {event_type!r} ignored"
        event.save(update_fields=["error"])
        return JsonResponse({"status": "ok", "reason": event.error})
    # Zainpay asks for a 200 straight away; verifying and confirming (Zainpay API call,
    # emails) happens in the background. If that's interrupted, reconcile_payments finishes it.
    run_in_background(process_webhook_event, event.pk)
    return JsonResponse({"status": "ok", "reason": "accepted"})


def process_webhook_event(event_id: int):
    event = WebhookEvent.objects.get(pk=event_id)
    try:
        payment = Payment.objects.filter(reference=event.reference).first() if event.reference else None
        if payment is None:
            event.error = "unknown txnRef"
        else:
            services.process_payment(payment)
            event.processed, event.error = True, ""
    except GatewayError as exc:
        event.error = f"verify failed: {exc}"[:1000]
    except Exception as exc:  # logged; reconcile_payments will retry the payment
        logger.exception("Zainpay webhook processing error (event %s)", event.pk)
        event.error = f"error: {exc}"[:1000]
    event.save(update_fields=["processed", "error"])


# ---------------------------------------------------------------------------
# Development simulator: a stand-in for Zainpay's hosted checkout page.
# ---------------------------------------------------------------------------
SIM_PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Zainpay sandbox (simulated)</title><style>
body{{font-family:system-ui,sans-serif;background:#f4f7ff;margin:0;display:grid;place-items:center;min-height:100vh;color:#0b1d55}}
.card{{background:#fff;border-radius:16px;box-shadow:0 10px 40px rgba(11,29,85,.12);padding:28px;width:min(420px,92vw)}}
.tag{{display:inline-block;background:#fff6e3;color:#9a6b00;border-radius:99px;padding:3px 10px;font-size:.75rem;font-weight:600}}
h1{{font-size:1.2rem;margin:12px 0 4px}} .amt{{font-size:2rem;font-weight:800;margin:8px 0}} p{{color:#55618a;font-size:.9rem}}
button{{width:100%;padding:12px;border-radius:10px;border:0;font-weight:700;font-size:.95rem;margin-top:10px;cursor:pointer}}
.ok{{background:#1846d6;color:#fff}} .bad{{background:#fdeef0;color:#dc2f45}} .off{{background:#eef1f8;color:#55618a}}
</style></head><body><form class="card" method="post">
<input type="hidden" name="csrfmiddlewaretoken" value="{csrf}">
<span class="tag">SIMULATED CHECKOUT · no real money</span><h1>Zainpay sandbox</h1>
<p>{description}<br>Ref: <code>{ref}</code></p><div class="amt">&#8358;{amount}</div>
<button class="ok" name="outcome" value="success">Pay successfully</button>
<button class="bad" name="outcome" value="failed">Decline payment</button>
<button class="off" name="outcome" value="cancel">Cancel and go back</button>
</form></body></html>"""


@require_http_methods(["GET", "POST"])
def simulator_checkout(request, ref):
    if settings.PAYMENT_GATEWAY != "simulator":
        raise Http404
    payment = get_object_or_404(Payment, reference=ref, gateway="simulator")
    sim = (payment.gateway_payload or {}).get("simulator", {})
    if request.method == "GET":
        return HttpResponse(SIM_PAGE.format(csrf=get_token(request), description=escape(payment.description),
                                            ref=escape(payment.reference), amount=f"{payment.amount + settings.ZAINPAY['PAYER_CHARGE']:,}"))
    outcome = request.POST.get("outcome")
    if outcome in ("success", "failed"):
        sim["outcome"] = outcome
        payment.gateway_payload = {**payment.gateway_payload, "simulator": sim}
        payment.save(update_fields=["gateway_payload", "updated_at"])
    return HttpResponseRedirect((sim.get("callback") or "/api/payments/zainpay/callback") + "?" + urlencode({"txnRef": ref}))


# ---------------------------------------------------------------------------
# Staff: transactions list and duplicate refunds
# ---------------------------------------------------------------------------
class StaffPaymentRowSerializer(PaymentSerializer):
    isDuplicate = serializers.SerializerMethodField()
    refundOf = serializers.CharField(source="parent.reference", default=None)

    class Meta(PaymentSerializer.Meta):
        fields = PaymentSerializer.Meta.fields + ["isDuplicate", "refundOf"]

    def get_isDuplicate(self, obj):
        return (obj.kind == Payment.Kind.CHARGE and obj.status == Payment.Status.SUCCESS and obj.application_id is not None
                and obj.pk not in self.context["counted"])


class StaffPaymentsView(APIView):
    """GET ?status=&purpose=&kind=&q= → {results, summary}."""

    permission_classes = [IsPortalStaff]

    def get(self, request):
        p = request.query_params
        qs = Payment.objects.select_related("application__programme", "application__enrollment__student", "parent")
        for key, field in (("status", "status"), ("purpose", "purpose"), ("kind", "kind")):
            if p.get(key):
                qs = qs.filter(**{field: p[key]})
        if p.get("q"):
            q = p["q"].strip()
            qs = qs.filter(Q(reference__icontains=q) | Q(name__icontains=q) | Q(email__icontains=q)
                           | Q(application__number__icontains=q))
        counted = services.counted_charge_ids()
        rows = StaffPaymentRowSerializer(qs.order_by("-created_at")[:2000], many=True, context={"counted": counted}).data
        charges = Payment.objects.filter(kind=Payment.Kind.CHARGE)
        total = lambda **f: charges.filter(**f).aggregate(t=Sum("amount"))["t"] or 0  # noqa: E731
        return Response({"results": rows, "summary": {
            "collected": total(status=Payment.Status.SUCCESS) + total(status=Payment.Status.REFUNDED),
            "applicationFees": total(status__in=[Payment.Status.SUCCESS, Payment.Status.REFUNDED], purpose=Payment.Purpose.APPLICATION_FEE),
            "programmeFees": total(status__in=[Payment.Status.SUCCESS, Payment.Status.REFUNDED], purpose=Payment.Purpose.PROGRAMME_FEE),
            "refunded": Payment.objects.filter(kind=Payment.Kind.REFUND).aggregate(t=Sum("amount"))["t"] or 0,
            "pending": charges.filter(status=Payment.Status.PENDING).count(),
            "failed": charges.filter(status=Payment.Status.FAILED).count(),
            "duplicates": sum(1 for r in rows if r["isDuplicate"]),
        }})


class RefundSerializer(serializers.Serializer):
    transferRef = serializers.CharField(max_length=100)
    note = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class StaffRefundView(APIView):
    """Record a refund already sent by bank transfer (duplicate payments only)."""

    permission_classes = [IsPortalStaff]

    def post(self, request, ref):
        payment = get_object_or_404(Payment, reference=ref, kind=Payment.Kind.CHARGE)
        data = RefundSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        refund = services.refund_duplicate(payment, request.user, data.validated_data["transferRef"], data.validated_data["note"])
        return Response(PaymentSerializer(refund).data, status=201)
