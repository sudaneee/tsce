import hashlib
import hmac
import json
from datetime import date
from io import StringIO
from unittest import mock

import requests
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.academics.models import Enrollment, Student
from apps.accounts.models import User
from apps.admissions.models import Application
from apps.comms.models import Notification
from apps.core.models import SiteSettings
from apps.programmes.models import Cohort, Programme

from . import services
from .gateways import FAILED, PENDING, SUCCESS, GatewayError, VerifyResult, ZainpayGateway
from .models import Payment, WebhookEvent

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
ZP = {"ENVIRONMENT": "sandbox", "BASE_URL": "https://sandbox.zainpay.ng", "PUBLIC_KEY": "pk-test", "SECRET_KEY": "",
      "ZAINBOX_CODE": "ZB-TSCE", "CALLBACK_URL": "", "PAYER_CHARGE": 0, "CHANNELS": [], "RECONCILE_LOOKBACK_HOURS": 720}
OCT_1 = date(2026, 10, 1)


def resp(status, body):
    r = mock.Mock()
    r.status_code = status
    r.text = json.dumps(body)
    r.json.return_value = body
    return r


def on(day):
    return mock.patch("django.utils.timezone.localdate", return_value=day)


# ---------------------------------------------------------------------------
# Zainpay client — response shapes learned from live sandbox use (Glittering)
# ---------------------------------------------------------------------------
@override_settings(ZAINPAY=ZP)
class ZainpayGatewayTests(TestCase):
    def setUp(self):
        self.gw = ZainpayGateway()
        self.payment = Payment(reference="TSCE-ZP-20261001-000001", amount=50000, email="a@example.com")

    @mock.patch("apps.payments.gateways.requests.post")
    def test_initialize_payload_and_url(self, post):
        post.return_value = resp(200, {"code": "00", "data": "https://checkout.zainpay.ng/pay/abc"})
        url = self.gw.initialize(self.payment, "https://x/cb", mobile="08031234567")
        self.assertEqual(url, "https://checkout.zainpay.ng/pay/abc")
        args, kwargs = post.call_args
        self.assertEqual(args[0], "https://sandbox.zainpay.ng/zainbox/card/initialize/payment")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer pk-test")
        body = kwargs["json"]
        self.assertEqual((body["amount"], body["txnRef"], body["zainboxCode"]), ("50000", "TSCE-ZP-20261001-000001", "ZB-TSCE"))
        self.assertNotIn("paymentChannels", body)  # all channels unless configured

    @mock.patch("apps.payments.gateways.requests.post")
    def test_payer_charge_and_channels_only_affect_the_gateway_request(self, post):
        post.return_value = resp(200, {"data": {"redirectUrl": "https://checkout/x"}})
        with override_settings(ZAINPAY={**ZP, "PAYER_CHARGE": 300, "CHANNELS": ["bank_transfer"]}):
            self.gw.initialize(self.payment, "https://x/cb", mobile="")
        body = post.call_args.kwargs["json"]
        self.assertEqual((body["amount"], body["paymentChannels"]), ("50300", ["bank_transfer"]))
        self.assertEqual(self.payment.amount, 50000)

    @mock.patch("apps.payments.gateways.requests.post")
    def test_initialize_errors(self, post):
        post.return_value = resp(400, {"code": "04", "description": "Invalid zainbox"})
        with self.assertRaisesMessage(GatewayError, "Invalid zainbox"):
            self.gw.initialize(self.payment, "https://x/cb", mobile="")
        post.side_effect = requests.ConnectionError("down")
        with self.assertRaises(GatewayError):
            self.gw.initialize(self.payment, "https://x/cb", mobile="")
        with override_settings(ZAINPAY={**ZP, "PUBLIC_KEY": ""}), self.assertRaisesMessage(GatewayError, "not configured"):
            self.gw.initialize(self.payment, "https://x/cb", mobile="")

    @mock.patch("apps.payments.gateways.requests.get")
    def test_verify_flat_deposit_record_is_success(self, get):
        get.return_value = resp(200, {"txnRef": "R1", "amountAfterCharges": 49800, "paymentChannel": "card"})
        r = self.gw.verify("R1")
        self.assertEqual((r.status, r.channel), (SUCCESS, "card"))
        self.assertIn("/virtual-account/wallet/deposit/verify/v2/R1", get.call_args.args[0])

    @mock.patch("apps.payments.gateways.requests.get")
    def test_verify_wrapped_deposit_record_is_success(self, get):
        get.return_value = resp(200, {"status": "200 OK", "code": "00", "data": {"txnRef": "R1", "txnType": "deposit"}})
        self.assertEqual(self.gw.verify("R1").status, SUCCESS)

    @mock.patch("apps.payments.gateways.requests.get")
    def test_ambiguous_not_found_falls_back_to_reconcile(self, get):
        not_found = resp(400, {"code": "04", "description": "Txn not found"})
        get.side_effect = [not_found, resp(200, {"code": "00", "data": {"txnStatus": "success"}})]
        self.assertEqual(self.gw.verify("R1").status, SUCCESS)
        get.side_effect = [not_found, resp(200, {"code": "00", "data": {"txnStatus": "failed"}})]
        self.assertEqual(self.gw.verify("R1").status, FAILED)
        get.side_effect = [not_found, resp(400, {"code": "04", "description": "Invalid txnRef"})]
        self.assertEqual(self.gw.verify("R1").status, PENDING)  # never "failed" on ambiguity


# ---------------------------------------------------------------------------
# Payment flow (simulator gateway)
# ---------------------------------------------------------------------------
@override_settings(CACHES=LOCMEM, PAYMENT_GATEWAY="simulator", ZAINPAY=ZP)
class PaymentFlowTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_school", stdout=StringIO())

    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.staff = User.objects.create_user("rabi@tsce.edu.ng", "x-Pass-2026!", full_name="Rabi", role="staff")
        self.user = User.objects.create_user("aisha@example.com", "x-Pass-2026!", full_name="Aisha Garba", role="applicant")
        self.app = self.make_app(self.user)
        self.client.login(email="aisha@example.com", password="x-Pass-2026!")

    def make_app(self, user, number="TSCE/APP/2026/00001", programme="fullstack", **extra):
        prog = Programme.objects.get(slug=programme)
        fields = dict(number=number, user=user, first_name="Aisha", last_name="Garba", gender="Female",
                      dob=date(2002, 5, 14), phone="0803 123 4567", email=user.email, address="Samaru, Zaria",
                      state="Kaduna", lga="Zaria", qualification="OND", institution="NBP", waec_status="Not Applicable",
                      programme=prog, cohort=Cohort.objects.get(), schedule=prog.schedules[0], fee=prog.fee,
                      amount_payable=prog.fee)
        fields.update(extra)
        return Application.objects.create(**fields)

    def csrf(self):
        return {"HTTP_X_CSRFTOKEN": self.client.get("/api/auth/csrf").json()["csrfToken"]}

    def initialize(self, number="TSCE/APP/2026/00001"):
        with on(OCT_1):
            return self.client.post("/api/payments/initialize", {"applicationId": number}, format="json", **self.csrf())

    def checkout(self, outcome):
        """Initialize → simulated checkout page → callback; returns the final redirect."""
        res = self.initialize()
        self.assertEqual(res.status_code, 200, res.content)
        url = res.json()["checkoutUrl"]
        self.assertEqual(self.client.get(url).status_code, 200)
        back = self.client.post(url, {"outcome": outcome}, **self.csrf())
        self.assertEqual(back.status_code, 302)
        self.assertIn("/api/payments/zainpay/callback?txnRef=", back["Location"])
        return self.client.get(back["Location"]), res.json()["ref"]


class PaymentFlowTests(PaymentFlowTestCase):
    def test_successful_payment_activates_the_student(self):
        final, ref = self.checkout("success")
        self.assertEqual(final["Location"], f"/pages/success.html?ref={ref}")
        self.assertRegex(ref, r"^TSCE-ZP-\d{8}-\d{6}$")

        self.app.refresh_from_db()
        self.assertEqual((self.app.payment_status, self.app.status), ("Paid", "Pending"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, "student")
        student = Student.objects.get(user=self.user)
        self.assertRegex(student.student_no, r"^TSCE/\d{4}/00001$")
        enrollment = Enrollment.objects.get()
        self.assertEqual((enrollment.status, enrollment.amount_paid, enrollment.start_date), ("Admission Pending", 50000, date(2026, 10, 12)))
        self.assertTrue(Notification.objects.filter(recipient=self.user, title="Payment successful").exists())
        self.assertTrue(Notification.objects.filter(recipient=self.staff, title="Payment received").exists())

        detail = self.client.get(f"/api/payments/{ref}").json()
        self.assertEqual((detail["status"], detail["applicationId"], detail["studentId"]), ("SUCCESS", self.app.number, student.student_no))
        self.assertEqual(self.client.get(f"/api/applications/{self.app.number}").json()["txRef"], ref)

        # Every later confirmation path is a no-op
        self.client.get(f"/api/payments/zainpay/callback?txnRef={ref}")
        self.client.post(f"/api/payments/{ref}/check", **self.csrf())
        call_command("reconcile_payments", stdout=StringIO())
        self.assertEqual(Enrollment.objects.count(), 1)
        self.assertEqual(Notification.objects.filter(recipient=self.user, title="Payment successful").count(), 1)

    def test_accepted_applicant_is_enrolled_on_payment(self):
        Application.objects.filter(pk=self.app.pk).update(status="Accepted")
        self.checkout("success")
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, "Enrolled")
        self.assertEqual(Enrollment.objects.get().status, "Active")

    def test_declined_then_retry(self):
        final, ref = self.checkout("failed")
        self.assertIn("/pages/payment.html?result=failed", final["Location"])
        self.assertEqual(Payment.objects.get(reference=ref).status, "FAILED")
        self.app.refresh_from_db()
        self.assertEqual(self.app.payment_status, "Failed")
        final, ref2 = self.checkout("success")
        self.assertNotEqual(ref, ref2)
        self.assertTrue(final["Location"].startswith("/pages/success.html"))

    def test_abandoned_checkout_stays_pending(self):
        final, ref = self.checkout("cancel")
        self.assertIn("result=pending", final["Location"])
        self.assertEqual(Payment.objects.get(reference=ref).status, "PENDING")
        self.app.refresh_from_db()
        self.assertEqual(self.app.payment_status, "Unpaid")

    def test_callback_without_txnref_uses_only_this_browsers_session(self):
        res = self.initialize()
        ref = res.json()["ref"]
        self.client.post(res.json()["checkoutUrl"], {"outcome": "success"}, **self.csrf())
        final = self.client.get("/api/payments/zainpay/callback")
        self.assertEqual(final["Location"], f"/pages/success.html?ref={ref}")
        stranger = APIClient()
        self.assertIn("result=unknown", stranger.get("/api/payments/zainpay/callback")["Location"])

    def test_early_bird_is_rechecked_at_payment_time(self):
        Application.objects.filter(pk=self.app.pk).update(discount_type="earlybird", discount_pct=15,
                                                            discount_amount=7500, amount_payable=42500)
        res = self.initialize()  # 1 October: the early bird has ended
        self.assertEqual(res.json()["amount"], 50000)
        self.app.refresh_from_db()
        self.assertEqual((self.app.amount_payable, self.app.discount_type), (50000, ""))
        self.assertIn("Early-bird period ended", self.app.events.last().text)

    def test_refusals(self):
        Programme.objects.filter(slug="fullstack").update(capacity=1)
        other = User.objects.create_user("b@example.com", "x-Pass-2026!", full_name="B", role="student")
        self.make_app(other, number="TSCE/APP/2026/00002", payment_status="Paid")
        self.assertEqual(self.initialize().json()["code"], "programme_full")
        Programme.objects.filter(slug="fullstack").update(capacity=40)

        Application.objects.filter(pk=self.app.pk).update(status="Rejected")
        self.assertEqual(self.initialize().json()["code"], "application_rejected")
        Application.objects.filter(pk=self.app.pk).update(status="Pending", payment_status="Paid")
        self.assertEqual(self.initialize().json()["code"], "already_paid")

        self.assertEqual(self.initialize("TSCE/APP/2026/00002").status_code, 404)  # not yours
        self.assertEqual(APIClient().post("/api/payments/initialize", {"applicationId": self.app.number}).status_code, 401)

    def test_payment_visibility(self):
        _, ref = self.checkout("success")
        User.objects.create_user("c@example.com", "x-Pass-2026!", full_name="C")
        other = APIClient()
        other.login(email="c@example.com", password="x-Pass-2026!")
        self.assertEqual(other.get(f"/api/payments/{ref}").status_code, 404)
        other.login(email="rabi@tsce.edu.ng", password="x-Pass-2026!")
        self.assertEqual(other.get(f"/api/payments/{ref}").status_code, 200)

    def test_double_payment_is_flagged_not_double_enrolled(self):
        first = self.initialize().json()
        second = self.initialize().json()
        for p in (first, second):
            self.client.post(p["checkoutUrl"], {"outcome": "success"}, **self.csrf())
            self.client.get(f"/api/payments/zainpay/callback?txnRef={p['ref']}")
        self.assertEqual(Payment.objects.filter(status="SUCCESS").count(), 2)
        self.assertEqual(Enrollment.objects.count(), 1)
        self.assertTrue(Notification.objects.filter(recipient=self.staff, title="Duplicate payment — refund needed").exists())

    def test_gateway_failure_at_initialize(self):
        with mock.patch("apps.payments.gateways.SimulatorGateway.initialize", side_effect=GatewayError("down")):
            res = self.initialize()
        self.assertEqual((res.status_code, res.json()["code"]), (502, "gateway_unavailable"))
        self.assertEqual(Payment.objects.get().status, "FAILED")

    def test_simulator_page_is_unavailable_with_real_gateway(self):
        ref = self.initialize().json()["ref"]
        with override_settings(PAYMENT_GATEWAY="zainpay"):
            self.assertEqual(self.client.get(f"/api/payments/simulator/{ref}").status_code, 404)


@override_settings(ZAINPAY={**ZP, "SECRET_KEY": "whsec-test"})
class WebhookTests(PaymentFlowTestCase):
    def post_webhook(self, body, secret="whsec-test"):
        raw = json.dumps(body).encode()
        sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        return APIClient().post("/api/payments/zainpay/webhook", raw, content_type="application/json",
                                HTTP_ZAINPAY_SIGNATURE=sig)

    def pending_zainpay_payment(self):
        return Payment.objects.create(reference="TSCE-ZP-20261001-000099", application=self.app, user=self.user,
                                      name="Aisha", email=self.user.email, description="x", amount=50000,
                                      gateway="zainpay", checkout_url="https://checkout/x")

    @mock.patch("apps.payments.gateways.ZainpayGateway.verify", return_value=VerifyResult(SUCCESS, {"txnRef": "x"}))
    def test_signed_deposit_event_confirms_after_reverifying(self, verify):
        payment = self.pending_zainpay_payment()
        res = self.post_webhook({"event": "deposit.successful", "data": {"txnRef": payment.reference}})
        self.assertEqual(res.status_code, 200)
        verify.assert_called_once_with(payment.reference)  # body is never trusted on its own
        payment.refresh_from_db()
        self.assertEqual(payment.status, "SUCCESS")
        self.assertTrue(WebhookEvent.objects.get().processed)
        # Retried webhook: no second verify, nothing changes
        self.post_webhook({"event": "deposit.successful", "data": {"txnRef": payment.reference}})
        self.assertEqual(verify.call_count, 1)
        self.assertEqual(Enrollment.objects.count(), 1)

    @mock.patch("apps.payments.gateways.ZainpayGateway.verify")
    def test_bad_signature_is_rejected_and_logged(self, verify):
        payment = self.pending_zainpay_payment()
        res = self.post_webhook({"event": "deposit.successful", "data": {"txnRef": payment.reference}}, secret="wrong")
        self.assertEqual(res.status_code, 400)
        verify.assert_not_called()
        event = WebhookEvent.objects.get()
        self.assertEqual((event.signature_valid, event.processed, event.error), (False, False, "invalid signature"))

    @mock.patch("apps.payments.gateways.ZainpayGateway.verify")
    def test_irrelevant_events_are_acknowledged(self, verify):
        self.assertEqual(self.post_webhook({"event": "transfer.success", "data": {"txnRef": "X"}}).status_code, 200)
        self.assertEqual(self.post_webhook({"event": "deposit.successful", "data": {"txnRef": "UNKNOWN"}}).status_code, 200)
        verify.assert_not_called()

    @mock.patch("apps.payments.gateways.ZainpayGateway.verify", side_effect=GatewayError("timeout"))
    def test_gateway_error_still_answers_200(self, verify):
        payment = self.pending_zainpay_payment()
        res = self.post_webhook({"event": "deposit.successful", "data": {"txnRef": payment.reference}})
        self.assertEqual(res.status_code, 200)
        self.assertIn("verify failed", WebhookEvent.objects.get().error)

    @mock.patch("apps.payments.gateways.ZainpayGateway.verify", return_value=VerifyResult(SUCCESS, {"txnRef": "x"}))
    def test_reconcile_command_confirms_missed_payments(self, verify):
        payment = self.pending_zainpay_payment()
        out = StringIO()
        call_command("reconcile_payments", stdout=out)
        self.assertIn("confirmed=1", out.getvalue())
        payment.refresh_from_db()
        self.assertEqual(payment.status, "SUCCESS")
