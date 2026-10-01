"""
Payment gateways. Only the backend talks to Zainpay and only the backend holds
its keys. Business logic (services.py) is gateway-agnostic: it calls
`initialize()` and `verify()` and gets the same result shapes from both.

ZainpayGateway is ported from the Glittering Field Academy integration
(glittering/payments/services.py), which was corrected against Zainpay's docs
after live sandbox testing:

1. POST /zainbox/card/initialize/payment          → response "data" is the hosted checkout URL
2. The payer completes checkout on Zainpay's page
3. Zainpay redirects the browser to callBackUrl?txnRef=<ref> and/or POSTs a webhook
4. GET /virtual-account/wallet/deposit/verify/v2/{txnRef}
     Success arrives in two shapes: a flat deposit record (txnRef at the top,
     no "code"), or the same record wrapped as {"code":"00","data":{…}}.
     HTTP 400 {"code":"04","description":"Txn not found"} is AMBIGUOUS — it
     covers pending, failed and unknown alike, and has been seen for payments
     that later succeeded. Never treat it as final.
5. On ambiguity: GET /virtual-account/wallet/transaction/reconcile/card-payment?txnRef=
     → {"code":"00","data":{"txnStatus":"success"|"failed"}} once Zainpay can tell.

Authentication: "Authorization: Bearer <ZAINPAY_PUBLIC_KEY>" (a JWT from the
merchant dashboard). The secret key is only used to check webhook signatures.
Amounts sent to these endpoints are in naira.
"""
import logging
from dataclasses import dataclass, field

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

SUCCESS, PENDING, FAILED = "success", "pending", "failed"


class GatewayError(Exception):
    """The gateway could not be reached or answered with something unusable."""


@dataclass
class VerifyResult:
    status: str                       # success | pending | failed
    raw: dict = field(default_factory=dict)
    channel: str = ""
    failure_reason: str = ""


def _zainpay_cfg():
    return settings.ZAINPAY


class ZainpayGateway:
    name = "zainpay"

    def _base(self):
        return _zainpay_cfg()["BASE_URL"].rstrip("/")

    def _headers(self):
        return {
            "Authorization": f"Bearer {_zainpay_cfg()['PUBLIC_KEY']}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _json(self, resp, what):
        raw = resp.text or ""
        logger.info("Zainpay %s — HTTP %s — %s", what, resp.status_code, raw[:400])
        if not raw.strip():
            raise GatewayError(f"Empty response from Zainpay (HTTP {resp.status_code})")
        try:
            return resp.json()
        except ValueError:
            raise GatewayError(f"Unexpected response from Zainpay (HTTP {resp.status_code})")

    def initialize(self, payment, callback_url: str, mobile: str) -> str:
        """Starts a hosted checkout and returns the URL to send the payer to."""
        cfg = _zainpay_cfg()
        if not cfg["PUBLIC_KEY"] or not cfg["ZAINBOX_CODE"]:
            raise GatewayError("Zainpay is not configured (ZAINPAY_PUBLIC_KEY / ZAINPAY_ZAINBOX_CODE).")
        payload = {
            # Any payer-borne charge is added only here, never to our own records.
            "amount": str(payment.amount + cfg["PAYER_CHARGE"]),
            "txnRef": payment.reference,
            "mobileNumber": mobile or "08000000000",
            "emailAddress": payment.email,
            "zainboxCode": cfg["ZAINBOX_CODE"],
            "callBackUrl": callback_url,
        }
        if cfg["CHANNELS"]:
            payload["paymentChannels"] = cfg["CHANNELS"]
        try:
            resp = requests.post(f"{self._base()}/zainbox/card/initialize/payment", json=payload,
                                 headers=self._headers(), timeout=30)
        except requests.RequestException as exc:
            raise GatewayError(f"Couldn't reach Zainpay: {exc}") from exc
        result = self._json(resp, f"initialize {payment.reference}")
        data = result.get("data")
        if isinstance(data, str) and data.startswith("http"):
            return data
        if isinstance(data, dict) and (data.get("redirectUrl") or data.get("paymentUrl")):
            return data.get("redirectUrl") or data.get("paymentUrl")
        raise GatewayError(result.get("description") or result.get("message") or "Zainpay did not return a checkout link.")

    def verify(self, reference: str) -> VerifyResult:
        try:
            resp = requests.get(f"{self._base()}/virtual-account/wallet/deposit/verify/v2/{reference}",
                                headers=self._headers(), timeout=30)
        except requests.RequestException as exc:
            raise GatewayError(f"Couldn't reach Zainpay: {exc}") from exc
        result = self._json(resp, f"verify {reference}")

        record = result if "txnRef" in result else (result.get("data") if isinstance(result.get("data"), dict) else {})
        if resp.status_code == 200 and "txnRef" in record:
            channel = str(record.get("paymentChannel") or record.get("channel") or "").lower()
            return VerifyResult(SUCCESS, result, channel="card" if "card" in channel else "transfer" if channel else "")

        reconciled = self._reconcile(reference)
        return reconciled or VerifyResult(PENDING, result)

    def _reconcile(self, reference: str) -> VerifyResult | None:
        try:
            resp = requests.get(f"{self._base()}/virtual-account/wallet/transaction/reconcile/card-payment",
                                headers=self._headers(), params={"txnRef": reference}, timeout=30)
            result = resp.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Zainpay reconcile %s inconclusive: %s", reference, exc)
            return None
        logger.info("Zainpay reconcile %s — HTTP %s — %s", reference, resp.status_code, str(result)[:400])
        if str(result.get("code")) != "00":
            return None
        status = str((result.get("data") or {}).get("txnStatus", "")).lower()
        if status == SUCCESS:
            return VerifyResult(SUCCESS, result)
        if status == FAILED:
            return VerifyResult(FAILED, result, failure_reason="Zainpay reported the payment as failed.")
        return None


class SimulatorGateway:
    """
    Local stand-in for development and demos. Checkout happens on a page served
    by this backend (/api/payments/simulator/<ref>) where the tester chooses an
    outcome; verify() then reports that outcome.
    """

    name = "simulator"

    def initialize(self, payment, callback_url: str, mobile: str) -> str:
        payment.gateway_payload = {"simulator": {"callback": callback_url, "outcome": None}}
        payment.save(update_fields=["gateway_payload"])
        return f"/api/payments/simulator/{payment.reference}"

    def verify(self, reference: str) -> VerifyResult:
        from .models import Payment

        payment = Payment.objects.filter(reference=reference).first()
        sim = (payment.gateway_payload or {}).get("simulator", {}) if payment else {}
        outcome = sim.get("outcome")
        if outcome == "success":
            return VerifyResult(SUCCESS, {"simulator": sim}, channel=sim.get("channel", "card"))
        if outcome == "failed":
            return VerifyResult(FAILED, {"simulator": sim}, failure_reason="Card declined by issuing bank (simulated).")
        return VerifyResult(PENDING, {"simulator": sim})


GATEWAYS = {"zainpay": ZainpayGateway, "simulator": SimulatorGateway}


def get_gateway(name: str | None = None):
    """The configured gateway, or the one a stored payment was made with."""
    name = name or settings.PAYMENT_GATEWAY
    if name not in GATEWAYS:
        raise GatewayError(f"Unknown payment gateway {name!r}")
    return GATEWAYS[name]()
