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
from django.utils import timezone
from rest_framework.test import APIClient

from apps.academics.models import Enrollment, Student
from apps.accounts.models import User
from apps.admissions.models import Application, AwardRequest
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
# Payment flow (simulator gateway): application fee → admission → programme fee
# ---------------------------------------------------------------------------
APP_FEE, PROG_FEE = "application_fee", "programme_fee"


@override_settings(CACHES=LOCMEM, PAYMENT_GATEWAY="simulator", ZAINPAY=ZP,
                   EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PaymentFlowTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_school", stdout=StringIO())

    def setUp(self):
        cache.clear()
        self.client = APIClient(enforce_csrf_checks=True)
        self.staff = User.objects.create_user("rabi@tsce.edu.ng", "x-Pass-2026!", full_name="Rabi", role="staff")
        self.user = self.account("aisha@example.com", "Aisha Garba")
        self.app = self.make_app(self.user)
        self.client.force_login(self.user)

    def account(self, email, name, role="applicant"):
        return User.objects.create_user(email, "x-Pass-2026!", full_name=name, role=role, email_verified_at=timezone.now())

    def make_app(self, user, number="TSCE/APP/2026/00001", programme="fullstack", first="Aisha", **extra):
        prog = Programme.objects.get(slug=programme)
        fields = dict(number=number, user=user, first_name=first, last_name="Garba", gender="Female",
                      dob=date(2002, 5, 14), phone="0803 123 4567", email=user.email, address="Samaru, Zaria",
                      state="Kaduna", lga="Zaria", qualification="OND", institution="NBP", waec_status="Not Applicable",
                      programme=prog, cohort=Cohort.objects.get(), schedule=prog.schedules[0], application_fee=5000,
                      fee=prog.fee, amount_payable=prog.fee)
        fields.update(extra)
        return Application.objects.create(**fields)

    def csrf(self):
        return {"HTTP_X_CSRFTOKEN": self.client.get("/api/auth/csrf").json()["csrfToken"]}

    def initialize(self, purpose=APP_FEE, number="TSCE/APP/2026/00001"):
        with on(OCT_1):
            return self.client.post("/api/payments/initialize", {"applicationId": number, "purpose": purpose},
                                    format="json", **self.csrf())

    def checkout(self, outcome, purpose=APP_FEE, number="TSCE/APP/2026/00001"):
        """Initialize → simulated checkout page → callback; returns (final redirect, ref)."""
        res = self.initialize(purpose, number)
        self.assertEqual(res.status_code, 200, res.content)
        url = res.json()["checkoutUrl"]
        self.assertEqual(self.client.get(url).status_code, 200)
        back = self.client.post(url, {"outcome": outcome}, **self.csrf())
        self.assertIn("/api/payments/zainpay/callback?txnRef=", back["Location"])
        with on(OCT_1):
            return self.client.get(back["Location"]), res.json()["ref"]

    def refresh(self):
        self.app.refresh_from_db()
        return self.app


class TwoStepFlowTests(PaymentFlowTestCase):
    def test_application_fee_then_auto_admission_then_programme_fee(self):
        final, ref = self.checkout("success", APP_FEE)
        self.assertEqual(final["Location"], f"/pages/success.html?ref={ref}")
        self.assertEqual(Payment.objects.get(reference=ref).amount, 5000)
        app = self.refresh()
        self.assertEqual((app.status, app.payment_status), ("Admitted", "Unpaid"))
        self.assertIsNotNone(app.application_fee_paid_at)
        self.assertEqual(Student.objects.count(), 0)  # nobody is a student until the programme fee is paid
        self.assertTrue(Notification.objects.filter(recipient=self.user, title="Admission approved").exists())
        from django.core import mail
        self.assertTrue(any("admitted" in m.body for m in mail.outbox))

        final, ref2 = self.checkout("success", PROG_FEE)
        self.assertEqual(final["Location"], f"/pages/success.html?ref={ref2}")
        self.assertEqual(Payment.objects.get(reference=ref2).amount, 50000)
        app = self.refresh()
        self.assertEqual((app.status, app.payment_status), ("Enrolled", "Paid"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, "student")
        student = Student.objects.get(user=self.user)
        enrollment = Enrollment.objects.get()
        self.assertEqual((enrollment.status, enrollment.amount_paid), ("Active", 50000))
        detail = self.client.get(f"/api/payments/{ref2}").json()
        self.assertEqual((detail["purpose"], detail["studentId"]), (PROG_FEE, student.student_no))
        self.assertEqual(self.client.get(f"/api/applications/{app.number}").json()["txRef"], ref2)

        # Every later confirmation path is a no-op
        self.client.post(f"/api/payments/{ref2}/check", **self.csrf())
        call_command("reconcile_payments", stdout=StringIO())
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_order_is_enforced(self):
        self.assertEqual(self.initialize(PROG_FEE).json()["code"], "not_admitted")
        self.checkout("success", APP_FEE)
        self.assertEqual(self.initialize(APP_FEE).json()["code"], "already_paid")
        self.assertEqual(self.initialize("tuition").json()["code"], "invalid")

    def test_excellence_award_path(self):
        AwardRequest.objects.create(application=self.app, type="excellence", requested_pct=50, evidence="WAEC 2022 — 6 A's")
        self.checkout("success", APP_FEE)
        self.assertEqual(self.refresh().status, "Awaiting Verification")
        self.assertEqual(self.initialize(PROG_FEE).json()["code"], "not_admitted")

        url = f"/api/staff/applications/{self.app.number}/award"
        self.assertEqual(self.client.post(url, {"approve": True}, format="json", **self.csrf()).status_code, 403)
        self.client.force_login(self.staff)
        res = self.client.post(url, {"approve": True, "note": "Original WAEC seen"}, format="json", **self.csrf())
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual((res.json()["status"], res.json()["amountPayable"], res.json()["discountType"]),
                         ("Admitted", 25000, "excellence"))
        self.assertEqual(self.client.post(url, {"approve": True}, format="json", **self.csrf()).json()["code"], "no_pending_award")

        self.client.force_login(self.user)
        final, ref = self.checkout("success", PROG_FEE)
        self.assertEqual(Payment.objects.get(reference=ref).amount, 25000)
        self.assertEqual(self.refresh().status, "Enrolled")

    def test_declined_award_pays_full_price(self):
        AwardRequest.objects.create(application=self.app, type="excellence", requested_pct=50)
        self.checkout("success", APP_FEE)
        self.client.force_login(self.staff)
        res = self.client.post(f"/api/staff/applications/{self.app.number}/award", {"approve": False},
                               format="json", **self.csrf())
        self.assertEqual((res.json()["status"], res.json()["amountPayable"]), ("Admitted", 50000))
        self.assertEqual(AwardRequest.objects.get().status, "Rejected")

    def test_award_cannot_be_decided_before_the_fee_is_paid(self):
        AwardRequest.objects.create(application=self.app, type="excellence", requested_pct=50)
        self.client.force_login(self.staff)
        res = self.client.post(f"/api/staff/applications/{self.app.number}/award", {"approve": True},
                               format="json", **self.csrf())
        self.assertEqual(res.json()["code"], "fee_unpaid")

    def test_parent_pays_for_two_children(self):
        parent = self.account("rabi.musa@example.com", "Rabi Musa", role="parent")
        self.make_app(parent, number="TSCE/APP/2026/00010", first="Aisha", email="")
        self.make_app(parent, number="TSCE/APP/2026/00011", first="Umar", programme="network", email="")
        self.client.force_login(parent)
        for number in ("TSCE/APP/2026/00010", "TSCE/APP/2026/00011"):
            self.checkout("success", APP_FEE, number)
            self.checkout("success", PROG_FEE, number)
        children = Student.objects.filter(guardian=parent).order_by("first_name")
        self.assertEqual([c.first_name for c in children], ["Aisha", "Umar"])
        self.assertTrue(all(c.user is None and c.account == parent for c in children))
        parent.refresh_from_db()
        self.assertEqual(parent.role, "parent")  # a parent never becomes a "student"
        self.assertEqual(Enrollment.objects.filter(student__guardian=parent).count(), 2)

    def test_declined_then_retry(self):
        final, ref = self.checkout("failed", APP_FEE)
        self.assertIn("/pages/payment.html?result=failed", final["Location"])
        self.assertEqual(Payment.objects.get(reference=ref).status, "FAILED")
        self.assertEqual(self.refresh().status, "Pending")
        final, _ = self.checkout("success", APP_FEE)
        self.assertTrue(final["Location"].startswith("/pages/success.html"))

    def test_abandoned_checkout_stays_pending(self):
        final, ref = self.checkout("cancel", APP_FEE)
        self.assertIn("result=pending", final["Location"])
        self.assertEqual(Payment.objects.get(reference=ref).status, "PENDING")

    def test_callback_without_txnref_uses_only_this_browsers_session(self):
        res = self.initialize(APP_FEE)
        ref = res.json()["ref"]
        self.client.post(res.json()["checkoutUrl"], {"outcome": "success"}, **self.csrf())
        self.assertEqual(self.client.get("/api/payments/zainpay/callback")["Location"], f"/pages/success.html?ref={ref}")
        self.assertIn("result=unknown", APIClient().get("/api/payments/zainpay/callback")["Location"])

    def test_early_bird_is_judged_on_the_programme_fee_payment_date(self):
        Application.objects.filter(pk=self.app.pk).update(status="Admitted", application_fee_paid_at=timezone.now(),
                                                            discount_type="earlybird", discount_pct=15,
                                                            discount_amount=7500, amount_payable=42500)
        res = self.initialize(PROG_FEE)  # 1 October: the early bird has ended
        self.assertEqual(res.json()["amount"], 50000)
        self.assertIn("re-priced", self.refresh().events.last().text)

    def test_seats_are_taken_by_programme_fee_only(self):
        Programme.objects.filter(slug="fullstack").update(capacity=1)
        other = self.account("b@example.com", "B")
        self.make_app(other, number="TSCE/APP/2026/00002", status="Admitted", application_fee_paid_at=timezone.now())
        self.checkout("success", APP_FEE)  # admitted although another applicant is admitted too
        self.assertEqual(self.refresh().status, "Admitted")
        self.client.force_login(other)
        self.checkout("success", PROG_FEE, "TSCE/APP/2026/00002")  # takes the only seat
        self.client.force_login(self.user)
        self.assertEqual(self.initialize(PROG_FEE).json()["code"], "programme_full")

    def test_refusals(self):
        Application.objects.filter(pk=self.app.pk).update(status="Rejected")
        self.assertEqual(self.initialize(APP_FEE).json()["code"], "application_rejected")
        other = self.account("c@example.com", "C")
        self.make_app(other, number="TSCE/APP/2026/00003")
        self.assertEqual(self.initialize(APP_FEE, "TSCE/APP/2026/00003").status_code, 404)  # not yours
        anon = APIClient()
        self.assertEqual(anon.post("/api/payments/initialize", {"applicationId": self.app.number}).status_code, 401)

    def test_double_payment_is_flagged_not_double_admitted(self):
        first = self.initialize(APP_FEE).json()
        second = self.initialize(APP_FEE).json()
        for p in (first, second):
            self.client.post(p["checkoutUrl"], {"outcome": "success"}, **self.csrf())
            self.client.get(f"/api/payments/zainpay/callback?txnRef={p['ref']}")
        self.assertEqual(Payment.objects.filter(status="SUCCESS").count(), 2)
        self.assertEqual(self.app.events.filter(text="Admission approved automatically").count(), 1)
        self.assertTrue(Notification.objects.filter(recipient=self.staff, title="Duplicate payment — refund needed").exists())

    def test_gateway_failure_at_initialize(self):
        with mock.patch("apps.payments.gateways.SimulatorGateway.initialize", side_effect=GatewayError("down")):
            res = self.initialize(APP_FEE)
        self.assertEqual((res.status_code, res.json()["code"]), (502, "gateway_unavailable"))
        self.assertEqual(Payment.objects.get().status, "FAILED")

    def test_simulator_page_is_unavailable_with_real_gateway(self):
        ref = self.initialize(APP_FEE).json()["ref"]
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
        return Payment.objects.create(reference="TSCE-ZP-20261001-000099", purpose=APP_FEE, application=self.app,
                                      user=self.user, name="Aisha", email=self.user.email, description="x",
                                      amount=5000, gateway="zainpay", checkout_url="https://checkout/x")

    @mock.patch("apps.payments.gateways.ZainpayGateway.verify", return_value=VerifyResult(SUCCESS, {"txnRef": "x"}))
    def test_signed_deposit_event_confirms_after_reverifying(self, verify):
        payment = self.pending_zainpay_payment()
        res = self.post_webhook({"event": "deposit.successful", "data": {"txnRef": payment.reference}})
        self.assertEqual(res.status_code, 200)
        verify.assert_called_once_with(payment.reference)  # the body is never trusted on its own
        self.assertEqual(self.refresh().status, "Admitted")
        self.assertTrue(WebhookEvent.objects.get().processed)
        self.post_webhook({"event": "deposit.successful", "data": {"txnRef": payment.reference}})
        self.assertEqual(verify.call_count, 1)

    @mock.patch("apps.payments.gateways.ZainpayGateway.verify")
    def test_bad_signature_is_rejected_and_logged(self, verify):
        payment = self.pending_zainpay_payment()
        res = self.post_webhook({"event": "deposit.successful", "data": {"txnRef": payment.reference}}, secret="wrong")
        self.assertEqual(res.status_code, 400)
        verify.assert_not_called()
        self.assertEqual(WebhookEvent.objects.get().error, "invalid signature")

    @mock.patch("apps.payments.gateways.ZainpayGateway.verify")
    def test_irrelevant_events_are_acknowledged(self, verify):
        self.assertEqual(self.post_webhook({"event": "transfer.success", "data": {"txnRef": "X"}}).status_code, 200)
        self.assertEqual(self.post_webhook({"event": "deposit.successful", "data": {"txnRef": "UNKNOWN"}}).status_code, 200)
        verify.assert_not_called()

    @mock.patch("apps.payments.gateways.ZainpayGateway.verify", side_effect=GatewayError("timeout"))
    def test_gateway_error_still_answers_200(self, verify):
        payment = self.pending_zainpay_payment()
        self.assertEqual(self.post_webhook({"event": "deposit.successful", "data": {"txnRef": payment.reference}}).status_code, 200)
        self.assertIn("verify failed", WebhookEvent.objects.get().error)

    @mock.patch("apps.payments.gateways.ZainpayGateway.verify", return_value=VerifyResult(SUCCESS, {"txnRef": "x"}))
    def test_reconcile_command_confirms_missed_payments(self, verify):
        payment = self.pending_zainpay_payment()
        out = StringIO()
        call_command("reconcile_payments", stdout=out)
        self.assertIn("confirmed=1", out.getvalue())
        payment.refresh_from_db()
        self.assertEqual(payment.status, "SUCCESS")
