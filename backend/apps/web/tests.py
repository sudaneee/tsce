"""Server-rendered applicant pages: sign in, the 5-step application, paying, receipts."""
import shutil
import tempfile
from datetime import date
from io import StringIO
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from apps.accounts import services as account_services
from apps.accounts.models import User
from apps.admissions.models import Application, AwardRequest
from apps.core.models import SiteSettings
from apps.payments.models import Payment
from apps.programmes.models import Cohort, Programme

PW = "x-Pass-2026!"
OCT_1 = date(2026, 10, 1)
LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
PDF = b"%PDF-1.4\n% test\n"


def on(day):
    return mock.patch("django.utils.timezone.localdate", return_value=day)


@override_settings(CACHES=LOCMEM, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                   BACKGROUND_TASKS_INLINE=True, PAYMENT_GATEWAY="simulator")
class WebTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_school", stdout=StringIO())

    def setUp(self):
        cache.clear()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        o = override_settings(PRIVATE_MEDIA_ROOT=self.media)
        o.enable()
        self.addCleanup(o.disable)
        self.today = on(OCT_1)
        self.today.start()
        self.addCleanup(self.today.stop)
        self.client = Client()

    def account(self, email="aisha@example.com", role="applicant", verified=True, name="Aisha Garba"):
        return User.objects.create_user(email, PW, full_name=name, role=role, phone="0803 123 4567",
                                        email_verified_at=timezone.now() if verified else None)

    def make_app(self, user, number="TSCE/APP/2026/00001", programme="fullstack", **extra):
        prog = Programme.objects.get(slug=programme)
        fields = dict(number=number, user=user, first_name="Aisha", last_name="Garba", gender="Female",
                      dob=date(2002, 5, 14), phone="0803 123 4567", email=user.email, address="Samaru, Zaria",
                      state="Kaduna", lga="Zaria", qualification="OND", institution="NBP", waec_status="Not Applicable",
                      programme=prog, cohort=Cohort.objects.get(), schedule=prog.schedules[0], application_fee=5000,
                      fee=prog.fee, amount_payable=prog.fee + 5000, status="Admitted")
        fields.update(extra)
        return Application.objects.create(**fields)


# ---------------------------------------------------------------------------
class AccountPagesTests(WebTestCase):
    def test_login_goes_to_my_applications_or_next(self):
        self.account()
        res = self.client.post("/account/login/", {"email": "aisha@example.com", "password": PW, "remember": "on"})
        self.assertRedirects(res, "/my-applications/", fetch_redirect_response=False)
        self.client.logout()
        res = self.client.post("/account/login/?next=/apply/", {"email": "aisha@example.com", "password": PW, "next": "/apply/"})
        self.assertEqual(res["Location"], "/apply/")
        res = self.client.post("/account/login/", {"email": "aisha@example.com", "password": PW, "next": "https://evil.example/"})
        self.assertEqual(res["Location"], "/my-applications/")  # no open redirect

    def test_login_failures(self):
        self.account(verified=False)
        res = self.client.post("/account/login/", {"email": "aisha@example.com", "password": "wrong"})
        self.assertContains(res, "Incorrect email or password")
        res = self.client.post("/account/login/", {"email": "aisha@example.com", "password": PW})
        self.assertContains(res, "Please verify your email address first")
        self.assertEqual(len(mail.outbox), 1)

    def test_staff_login_goes_to_staff_portal(self):
        User.objects.create_user("rabi@tsce.edu.ng", PW, full_name="Rabi", role="staff", email_verified_at=timezone.now())
        res = self.client.post("/account/login/?role=staff", {"email": "rabi@tsce.edu.ng", "password": PW})
        self.assertEqual(res["Location"], "/staff/")

    def test_login_is_rate_limited(self):
        for _ in range(10):
            self.client.post("/account/login/", {"email": "x@example.com", "password": "nope"})
        self.assertContains(self.client.post("/account/login/", {"email": "x@example.com", "password": "nope"}), "Too many attempts")

    def test_register_then_verify_by_button(self):
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post("/account/register/", {"accountType": "parent", "fullName": "Rabi Musa", "email": "Rabi@Example.com",
                                                          "phone": "0803 555 1234", "password": "Parent-Pass-2026", "password2": "Parent-Pass-2026"})
        self.assertContains(res, "Check your email")
        user = User.objects.get(email="rabi@example.com")
        self.assertEqual(user.role, "parent")
        self.assertIn("/account/verify-email/?token=", mail.outbox[0].body)
        token = account_services.verification_token(user)
        page = self.client.get(f"/account/verify-email/?token={token}")
        self.assertContains(page, "Confirm my email")
        user.refresh_from_db()
        self.assertIsNone(user.email_verified_at)  # opening the link (or a link scanner) doesn't verify
        res = self.client.post("/account/verify-email/", {"token": token})
        self.assertRedirects(res, "/my-applications/", fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertIsNotNone(user.email_verified_at)
        self.client.logout()
        res = self.client.post("/account/verify-email/", {"token": token})  # an old link isn't a password
        self.assertEqual(res["Location"], "/account/login/")

    def test_register_validation_and_no_probing(self):
        res = self.client.post("/account/register/", {"accountType": "student", "fullName": "A", "email": "a@example.com",
                                                      "phone": "123", "password": "password", "password2": "different"})
        self.assertContains(res, "valid Nigerian phone number")
        self.assertContains(res, "The passwords don&#x27;t match")
        self.account()
        res = self.client.post("/account/register/", {"accountType": "student", "fullName": "Aisha", "email": "aisha@example.com",
                                                      "phone": "0803 123 4567", "password": "Some-Pass-2026", "password2": "Some-Pass-2026"})
        self.assertContains(res, "Check your email")  # same answer for an existing email
        self.assertEqual(User.objects.filter(email="aisha@example.com").count(), 1)

    def test_bad_token_offers_resend(self):
        self.assertContains(self.client.post("/account/verify-email/", {"token": "nope"}), "Send a new link")

    def test_forced_password_change(self):
        user = self.account()
        User.objects.filter(pk=user.pk).update(must_change_password=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get("/my-applications/")["Location"], "/account/password/?next=%2Fmy-applications%2F")
        res = self.client.post("/account/password/?next=/my-applications/", {"old_password": PW, "new_password1": "New-Pass-2026x",
                                                                            "new_password2": "New-Pass-2026x", "next": "/my-applications/"})
        self.assertEqual(res["Location"], "/my-applications/")
        user.refresh_from_db()
        self.assertFalse(user.must_change_password)

    def test_logout_is_post_only(self):
        self.client.force_login(self.account())
        self.assertEqual(self.client.get("/account/logout/").status_code, 405)
        self.assertEqual(self.client.post("/account/logout/")["Location"], "/account/login/?out=1")


# ---------------------------------------------------------------------------
class WizardTests(WebTestCase):
    PERSONAL = {"firstName": "Aisha", "middleName": "", "lastName": "Garba", "gender": "Female", "dob": "2002-05-14",
                "phone": "+234 803 123 4567", "state": "Kaduna", "address": "12 Samaru Road", "lga": "Zaria"}
    EDUCATION = {"qualification": "OND", "gradYear": "2023", "institution": "NBP", "waecStatus": "Available",
                 "waecYear": "2022", "numAs": "6"}
    PROGRAMME = {"programmeId": "fullstack", "schedule": "Weekend (Sat & Sun, 10:00am – 3:00pm)"}

    def setUp(self):
        super().setUp()
        self.user = self.account()
        self.client.force_login(self.user)

    def steps_1_to_3(self, education=None, **files):
        self.assertRedirects(self.client.post("/apply/1/", self.PERSONAL), "/apply/2/", fetch_redirect_response=False)
        self.assertRedirects(self.client.post("/apply/2/", {**(education or self.EDUCATION), **files}), "/apply/3/",
                             fetch_redirect_response=False)
        self.assertRedirects(self.client.post("/apply/3/", self.PROGRAMME), "/apply/4/", fetch_redirect_response=False)

    def test_five_steps_admit_and_show_the_invoice(self):
        self.assertEqual(self.client.get("/apply/")["Location"], "/apply/1/")
        self.steps_1_to_3()
        review = self.client.get("/apply/4/")
        self.assertContains(review, "Fee calculation")
        self.assertContains(review, "₦55,000")   # ₦50,000 + ₦5,000 application fee (early bird closed on 1 Oct)
        self.assertContains(review, "₦30,000")   # 50% option: ₦25,000 + ₦5,000
        self.assertContains(review, "Request the Excellence Award")  # eligible (2022, 6 A's)
        res = self.client.post("/apply/4/", {"awardRequest": "none", "declare": "on", "nav": "submit"})
        app = Application.objects.get()
        self.assertRedirects(res, f"/apply/done/{app.number}/", fetch_redirect_response=False)
        self.assertEqual((app.status, app.amount_payable, app.email, app.phone), ("Admitted", 55000, "aisha@example.com", "0803 123 4567"))
        done = self.client.get(res["Location"])
        self.assertContains(done, "Step 5 of 5")
        self.assertContains(done, "Admitted!")
        self.assertContains(done, f"/pay/{app.number}/")
        self.assertNotIn("apply_draft", self.client.session)

    def test_steps_validate_on_the_server(self):
        res = self.client.post("/apply/1/", {**self.PERSONAL, "phone": "12345", "dob": "2020-01-01"})
        self.assertContains(res, "valid Nigerian phone number")
        self.assertContains(res, "at least 12 years old")
        self.client.post("/apply/1/", self.PERSONAL)
        res = self.client.post("/apply/2/", {**self.EDUCATION, "waecYear": "", "gradYear": "2031"})
        self.assertContains(res, "Exam year is required")
        self.assertContains(res, "can&#x27;t be in the future")
        res = self.client.post("/apply/2/", {**self.EDUCATION, "resultFile": SimpleUploadedFile("w.pdf", b"MZ fake")})
        self.assertContains(res, "doesn&#x27;t look like a valid PDF")

    def test_steps_cant_be_skipped_and_back_keeps_answers(self):
        self.assertEqual(self.client.get("/apply/3/")["Location"], "/apply/1/")
        self.client.post("/apply/1/", self.PERSONAL)
        self.assertEqual(self.client.get("/apply/4/")["Location"], "/apply/2/")
        self.assertEqual(self.client.post("/apply/2/", {"nav": "back"})["Location"], "/apply/1/")
        self.assertContains(self.client.get("/apply/1/"), 'value="12 Samaru Road"')

    def test_upload_and_excellence_award_request(self):
        self.steps_1_to_3(resultFile=SimpleUploadedFile("waec.pdf", PDF, content_type="application/pdf"))
        self.assertContains(self.client.get("/apply/4/"), "result attached")
        self.client.post("/apply/4/", {"awardRequest": "excellence", "declare": "on"})
        app = Application.objects.get()
        self.assertEqual(app.status, "Awaiting Verification")
        self.assertTrue(app.waec_file.storage.exists(app.waec_file.name))
        self.assertEqual(AwardRequest.objects.get().status, "Pending")
        self.assertContains(self.client.get(f"/apply/done/{app.number}/"), "visit TSCE with the original WAEC/NECO result")

    def test_not_eligible_award_and_declaration_required(self):
        self.steps_1_to_3(education={**self.EDUCATION, "waecYear": "2018"})
        review = self.client.get("/apply/4/")
        self.assertContains(review, "Not eligible")
        self.assertNotContains(review, "Request the Excellence Award")
        self.assertContains(self.client.post("/apply/4/", {"awardRequest": "none"}), "Please confirm that the information is accurate")
        res = self.client.post("/apply/4/", {"awardRequest": "excellence", "declare": "on"})
        self.assertContains(res, "Excellence Award needs WAEC/NECO")
        self.assertEqual(Application.objects.count(), 0)

    def test_parent_child_email_and_duplicates(self):
        parent = self.account("rabi@example.com", role="parent", name="Rabi Musa")
        self.client.force_login(parent)
        self.client.post("/apply/1/", {**self.PERSONAL, "email": "Aisha.Musa@Example.com"})
        self.client.post("/apply/2/", self.EDUCATION)
        self.client.post("/apply/3/", self.PROGRAMME)
        self.client.post("/apply/4/", {"awardRequest": "none", "declare": "on"})
        self.assertEqual(Application.objects.get().email, "aisha.musa@example.com")
        self.client.get("/apply/?new=1")
        self.client.post("/apply/1/", self.PERSONAL)
        self.client.post("/apply/2/", self.EDUCATION)
        self.client.post("/apply/3/", self.PROGRAMME)
        res = self.client.post("/apply/4/", {"awardRequest": "none", "declare": "on"})
        self.assertContains(res, "already has an application")
        self.assertContains(res, "Open My applications")

    def test_programme_preselect_and_full_programme(self):
        self.client.get("/apply/?programme=network")
        self.client.post("/apply/1/", self.PERSONAL)
        self.client.post("/apply/2/", self.EDUCATION)
        self.assertContains(self.client.get("/apply/3/"), 'value="network" checked')
        Programme.objects.filter(slug="fullstack").update(capacity=0)
        self.client.post("/apply/3/", self.PROGRAMME)
        res = self.client.post("/apply/4/", {"awardRequest": "none", "declare": "on"})
        self.assertEqual(res["Location"], "/apply/3/")  # sent back to choose another programme
        self.assertContains(self.client.get("/apply/3/"), "is full")

    def test_gates(self):
        self.client.logout()
        self.assertContains(self.client.get("/apply/"), "Create an account to apply")
        self.client.force_login(self.account("u@example.com", verified=False))
        self.assertContains(self.client.get("/apply/1/"), "Verify your email first")
        self.client.force_login(self.user)
        SiteSettings.objects.update(accepting_applications=False)
        self.assertContains(self.client.get("/apply/1/"), "Applications are currently closed")
        self.client.force_login(User.objects.create_user("rabi@tsce.edu.ng", PW, full_name="Rabi", role="staff"))
        self.assertContains(self.client.get("/apply/"), "staff account")


# ---------------------------------------------------------------------------
class PayAndReceiptTests(WebTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.account()
        self.app = self.make_app(self.user)
        self.client.force_login(self.user)
        self.pay_url = f"/pay/{self.app.number}/"

    def checkout(self, plan="full", outcome="success", **amounts):
        page = self.client.get(self.pay_url)
        data = {"plan": plan, "amount_full": page.context["opts"].due_full}
        if page.context["opts"].half:
            data["amount_half"] = page.context["opts"].half
        data.update(amounts)
        res = self.client.post(self.pay_url, data)
        self.assertEqual(res.status_code, 302, getattr(res, "content", b"")[:500])
        self.assertIn("/api/payments/simulator/", res["Location"])
        back = self.client.post(res["Location"], {"outcome": outcome})
        return self.client.get(back["Location"])  # the Zainpay callback → our payment page

    def test_my_applications_offers_both_options(self):
        page = self.client.get("/my-applications/")
        self.assertContains(page, "Pay programme fee · ₦55,300")   # + the ₦300 Zainpay charge
        self.assertContains(page, "or pay 50% now · ₦30,300")
        self.assertContains(page, "+ application fee ₦5,000")

    def test_pay_in_full(self):
        page = self.client.get(self.pay_url)
        self.assertContains(page, 'id="planPick"')
        callback = self.checkout("full")
        pay = Payment.objects.get()
        self.assertEqual((pay.amount, pay.installment), (55000, Payment.Installment.FULL))
        self.assertEqual(callback["Location"], f"/payments/{pay.reference}/")
        done = self.client.get(callback["Location"])
        self.assertContains(done, "ENROLMENT CONFIRMED")
        self.assertContains(done, "TSCE/2026/00001")
        receipt = self.client.get(f"/payments/{pay.reference}/receipt/")
        self.assertContains(receipt, "PAID · VERIFIED")
        self.assertContains(receipt, "Application fee")
        self.assertContains(receipt, "₦55,000")
        self.assertContains(self.client.get(self.pay_url), "already paid")

    def test_pay_half_then_balance(self):
        self.checkout("half")
        first = Payment.objects.get()
        self.assertEqual((first.amount, first.installment), (30000, Payment.Installment.FIRST))
        done = self.client.get(f"/payments/{first.reference}/")
        self.assertContains(done, "balance of <b>₦25,000</b>")
        self.assertContains(self.client.get("/my-applications/"), "Pay balance · ₦25,300")
        page = self.client.get(self.pay_url)
        self.assertNotContains(page, 'id="planPick"')
        self.assertContains(page, "Programme fee balance")
        self.checkout("full")
        second = Payment.objects.order_by("-id").first()
        self.assertEqual((second.amount, second.installment), (25000, Payment.Installment.BALANCE))
        self.assertContains(self.client.get(f"/payments/{second.reference}/"), "PROGRAMME FEE FULLY PAID")
        self.app.refresh_from_db()
        self.assertEqual((self.app.payment_status, self.app.amount_paid), ("Paid", 55000))

    def test_price_change_is_shown_before_charging(self):
        res = self.client.post(self.pay_url, {"plan": "full", "amount_full": 46750, "amount_half": 23375})  # an old early-bird page
        self.assertContains(res, "The amount has changed to ₦55,000")
        self.assertEqual(Payment.objects.count(), 0)

    def test_installments_switched_off(self):
        SiteSettings.objects.update(allow_installments=False)
        self.assertNotContains(self.client.get(self.pay_url), 'id="planPick"')
        self.checkout("half")  # asking for half anyway gets the full amount
        self.assertEqual(Payment.objects.get().amount, 55000)

    def test_failed_and_pending(self):
        failed = self.checkout(outcome="failed")
        pay = Payment.objects.get()
        self.assertEqual(failed["Location"], f"/payments/{pay.reference}/")
        res = self.client.get(failed["Location"])
        self.assertEqual(res["Location"], f"{self.pay_url}?failed={pay.reference}")
        self.assertContains(self.client.get(res["Location"]), "didn't go through")
        pending = self.checkout(outcome="cancel")
        ref = Payment.objects.order_by("-id").first().reference
        self.assertEqual(pending["Location"], f"/payments/{ref}/?check=1")
        page = self.client.get(pending["Location"])
        self.assertContains(page, "confirming your payment")
        self.assertContains(page, f"/payments/{ref}/?check=2")  # refreshes itself
        last = self.client.get(f"/payments/{ref}/?check=10")
        self.assertNotContains(last, 'http-equiv="refresh"')
        self.assertContains(last, "you don't need to pay again")

    def test_other_peoples_pages_are_hidden(self):
        self.checkout()
        ref = Payment.objects.get().reference
        self.client.force_login(self.account("x@example.com", name="X"))
        self.assertEqual(self.client.get(self.pay_url).status_code, 404)
        self.assertEqual(self.client.get(f"/payments/{ref}/").status_code, 404)
        self.assertEqual(self.client.get(f"/payments/{ref}/receipt/").status_code, 404)

    def test_blocked_states(self):
        Application.objects.filter(pk=self.app.pk).update(status="Awaiting Verification")
        self.assertContains(self.client.get(self.pay_url), "Excellence Award verification pending")
        self.assertEqual(self.client.post(self.pay_url, {"plan": "full", "amount_full": 55000}).status_code, 200)
        self.assertEqual(Payment.objects.count(), 0)

    def test_csrf_is_enforced(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.pay_url, {"plan": "full", "amount_full": 55000}).status_code, 403)


class LegacyLinkTests(WebTestCase):
    def test_old_addresses_redirect(self):
        cases = {
            "/pages/login.html?role=staff": "/account/login/?role=staff",
            "/pages/register.html": "/account/register/",
            "/pages/verify-email.html?token=abc": "/account/verify-email/?token=abc",
            "/pages/application.html?programme=cad": "/apply/?programme=cad",
            "/pages/my-applications.html": "/my-applications/",
            "/pages/payment.html?app=TSCE/APP/2026/00001&purpose=programme_fee": "/pay/TSCE/APP/2026/00001/",
            "/pages/success.html?ref=TSCE-ZP-1": "/payments/TSCE-ZP-1/",
        }
        for old, new in cases.items():
            self.assertEqual(self.client.get(old)["Location"], new, old)
