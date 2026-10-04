import shutil
import tempfile
from datetime import date
from io import StringIO

from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import StaffProfile, User
from apps.comms.models import Notification
from apps.payments.models import Payment
from apps.programmes.models import Cohort, Programme

from .models import Application, AwardRequest

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
PW = "x-Pass-2026!"


@override_settings(CACHES=LOCMEM, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class StaffApiTestCase(TestCase):
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
        self.client = APIClient(enforce_csrf_checks=True)
        now = timezone.now()
        self.admin = User.objects.create_user("director@tsce.edu.ng", PW, full_name="Director", role="admin", email_verified_at=now)
        self.staff = User.objects.create_user("rabi@tsce.edu.ng", PW, full_name="Rabi Isa", role="staff", email_verified_at=now)
        self.applicant = User.objects.create_user("aisha@example.com", PW, full_name="Aisha Garba", role="applicant", email_verified_at=now)
        self.parent = User.objects.create_user("musa@example.com", PW, full_name="Musa Bello", role="parent", email_verified_at=now)
        self.a1 = self.make_app(self.applicant, 1, "Aisha", status="Admitted", amount_payable=55000)
        self.a2 = self.make_app(self.parent, 2, "Umar", programme="network", status="Awaiting Verification",
                                application_fee_paid_at=now)
        AwardRequest.objects.create(application=self.a2, type="excellence", requested_pct=50, evidence="WAEC 2024 — 7 A's")

    def make_app(self, user, n, first, programme="fullstack", **extra):
        prog = Programme.objects.get(slug=programme)
        fields = dict(number=f"TSCE/APP/2026/{n:05d}", user=user, first_name=first, last_name="Bello", gender="Male",
                      dob=date(2004, 1, 1), phone="0803 123 4567", email="", address="Zaria", state="Kaduna", lga="Zaria",
                      qualification="SSCE", institution="Barewa", waec_status="Available", waec_year=2024, num_as=7,
                      programme=prog, cohort=Cohort.objects.get(), schedule=prog.schedules[0], application_fee=5000,
                      fee=prog.fee, amount_payable=prog.fee)
        fields.update(extra)
        return Application.objects.create(**fields)

    def as_(self, user):
        self.client.force_login(user)
        return self

    def csrf(self):
        return {"HTTP_X_CSRFTOKEN": self.client.get("/api/auth/csrf").json()["csrfToken"]}

    def post(self, url, data=None):
        return self.client.post(url, data or {}, format="json", **self.csrf())

    def patch(self, url, data):
        return self.client.patch(url, data, format="json", **self.csrf())


class StaffApplicationsTests(StaffApiTestCase):
    def test_staff_only(self):
        self.assertEqual(self.client.get("/api/staff/applications").status_code, 401)
        self.as_(self.applicant)
        for url in ("/api/staff/applications", "/api/staff/summary", "/api/staff/payments", "/api/staff/search?q=ai"):
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_list_filters_and_counts(self):
        self.as_(self.staff)
        data = self.client.get("/api/staff/applications").json()
        self.assertEqual(data["counts"], {"Admitted": 1, "Awaiting Verification": 1, "all": 2})
        rows = self.client.get("/api/staff/applications", {"status": "Awaiting Verification"}).json()["results"]
        self.assertEqual([r["id"] for r in rows], ["TSCE/APP/2026/00002"])
        self.assertEqual((rows[0]["account"]["type"], rows[0]["award"]["status"]), ("parent", "Pending"))
        self.assertEqual(len(self.client.get("/api/staff/applications", {"q": "musa@"}).json()["results"]), 1)
        self.assertEqual(len(self.client.get("/api/staff/applications", {"award": "Pending"}).json()["results"]), 1)
        self.assertEqual(len(self.client.get("/api/staff/applications", {"programme": "fullstack"}).json()["results"]), 1)

    def test_detail_and_private_waec_file(self):
        self.a2.waec_file.save("result.pdf", ContentFile(b"%PDF-1.4 test"))
        self.as_(self.staff)
        d = self.client.get(f"/api/staff/applications/{self.a2.number}").json()
        self.assertEqual((d["account"]["email"], d["awardRequest"]["status"]), ("musa@example.com", "Pending"))
        res = self.client.get(d["waecFileUrl"])
        self.assertEqual((res.status_code, res["Content-Type"]), (200, "application/pdf"))
        self.assertEqual(b"".join(res.streaming_content), b"%PDF-1.4 test")
        self.as_(self.parent)  # even the owner can't fetch it through the staff URL
        self.assertEqual(self.client.get(d["waecFileUrl"]).status_code, 403)

    def test_reject_and_remind(self):
        self.as_(self.staff)
        res = self.post(f"/api/staff/applications/{self.a1.number}/remind")
        self.assertEqual(res.json()["reminded"], "programme fee")
        self.assertTrue(Notification.objects.filter(recipient=self.applicant, title__startswith="Reminder").exists())
        self.assertEqual(self.post(f"/api/staff/applications/{self.a2.number}/remind").json()["code"], "nothing_due")

        res = self.post(f"/api/staff/applications/{self.a2.number}/reject", {"note": "Result could not be verified"})
        self.assertEqual(res.json()["status"], "Rejected")
        self.assertEqual(AwardRequest.objects.get().status, "Rejected")
        self.assertTrue(Notification.objects.filter(recipient=self.parent, title="Application update").exists())
        self.assertEqual(self.post(f"/api/staff/applications/{self.a2.number}/reject").json()["code"], "invalid_state")

    def test_summary_and_search(self):
        self.as_(self.staff)
        s = self.client.get("/api/staff/summary").json()
        self.assertEqual((s["applications"]["total"], s["awardsToVerify"], s["intake"]), (2, 1, "October 2026 Cohort"))
        found = self.client.get("/api/staff/search", {"q": "umar"}).json()
        self.assertEqual([a["id"] for a in found["applications"]], ["TSCE/APP/2026/00002"])


class StaffPaymentsTests(StaffApiTestCase):
    def charge(self, ref, minutes):
        return Payment.objects.create(reference=ref, purpose="application_fee", application=self.a1, user=self.applicant,
                                      name="Aisha", email="aisha@example.com", description="x", amount=5000,
                                      gateway="zainpay", status="SUCCESS",
                                      verified_at=timezone.now() + timezone.timedelta(minutes=minutes))

    def test_duplicate_flagged_and_refund_recorded(self):
        first, dup = self.charge("TSCE-ZP-1", 0), self.charge("TSCE-ZP-2", 5)
        self.as_(self.staff)
        data = self.client.get("/api/staff/payments").json()
        flags = {r["ref"]: r["isDuplicate"] for r in data["results"]}
        self.assertEqual(flags, {"TSCE-ZP-1": False, "TSCE-ZP-2": True})
        self.assertEqual(data["summary"]["duplicates"], 1)

        self.assertEqual(self.post("/api/staff/payments/TSCE-ZP-1/refund", {"transferRef": "X"}).json()["code"], "not_refundable")
        res = self.post("/api/staff/payments/TSCE-ZP-2/refund", {"transferRef": "JAIZ-123", "note": "Paid twice"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual((res.json()["kind"], res.json()["amount"]), ("refund", 5000))
        dup.refresh_from_db()
        self.assertEqual(dup.status, "REFUNDED")
        self.assertEqual(self.post("/api/staff/payments/TSCE-ZP-2/refund", {"transferRef": "X"}).json()["code"], "not_refundable")
        self.assertTrue(Notification.objects.filter(recipient=self.applicant, title="Refund sent").exists())
        self.assertEqual(self.client.get("/api/staff/payments").json()["summary"]["refunded"], 5000)


class StaffAccountsTests(StaffApiTestCase):
    def test_admin_only(self):
        self.as_(self.staff)
        self.assertEqual(self.client.get("/api/staff/staff").status_code, 403)
        self.assertEqual(self.patch("/api/staff/settings", {"admissions": {}}).status_code, 403)
        self.assertEqual(self.client.get("/api/staff/settings").status_code, 200)  # staff may read

    def test_create_login_and_instructor(self):
        self.as_(self.admin)
        rows = self.client.get("/api/staff/staff").json()
        self.assertEqual({r["fullName"] for r in rows}, {"Director", "Rabi Isa"})  # profiles created for existing staff

        res = self.post("/api/staff/staff", {"fullName": "Kamal Shehu", "title": "Bursar", "department": "Finance",
                                             "email": "Bursary@tsce.edu.ng", "phone": "08031112222", "access": "staff"})
        self.assertEqual(res.status_code, 201, res.content)
        temp = res.json()["temporaryPassword"]
        self.assertRegex(res.json()["staff"]["staffNo"], r"^STF-\d{3}$")
        bursar = User.objects.get(email="bursary@tsce.edu.ng")
        self.assertTrue(bursar.check_password(temp) and bursar.must_change_password and bursar.email_verified)

        res = self.post("/api/staff/staff", {"fullName": "Engr. Musa Garba", "title": "Instructor — Networking",
                                             "department": "Academics", "access": "none"})
        self.assertEqual((res.json()["staff"]["access"], res.json()["temporaryPassword"]), ("none", None))
        self.assertEqual(self.post("/api/staff/staff", {"fullName": "X", "title": "Y", "department": "Academics",
                                                         "access": "staff"}).json()["code"], "invalid")  # login needs email

    def test_deactivate_and_self_protection(self):
        self.as_(self.admin)
        rows = {r["fullName"]: r for r in self.client.get("/api/staff/staff").json()}
        res = self.patch(f"/api/staff/staff/{rows['Rabi Isa']['id']}", {"status": "Inactive"})
        self.assertEqual(res.json()["staff"]["access"], "none")
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_active)
        self.assertEqual(self.patch(f"/api/staff/staff/{rows['Director']['id']}", {"access": "staff"}).json()["code"], "self_change")


class SettingsAndNotificationsTests(StaffApiTestCase):
    def test_update_admissions_and_discounts(self):
        self.as_(self.admin)
        cur = self.client.get("/api/staff/settings").json()
        self.assertEqual(cur["gateway"]["payerCharge"], 300)
        adm = {**cur["admissions"], "opens": "2026-09-01", "applicationFee": 6000, "earlyBirdDeadline": "2026-10-05"}
        res = self.patch("/api/staff/settings", {"admissions": adm})
        self.assertEqual(res.status_code, 200, res.content)
        site = self.client.get("/api/site").json()["settings"]
        self.assertEqual((site["admissions"]["applicationFee"], site["admissions"]["opens"]), (6000, "2026-09-01"))
        bad = self.patch("/api/staff/settings", {"admissions": {**adm, "opens": "2026-10-20"}})
        self.assertIn("closes", bad.json()["fields"])
        self.assertEqual(self.patch("/api/staff/settings", {"discounts": {"earlyBirdPct": 10, "excellencePct": 50,
                                                                           "excellenceMinYear": 2020, "excellenceMinAs": 5}}).status_code, 200)
        self.assertEqual(self.patch("/api/staff/settings", {"colours": {}}).json()["code"], "invalid")

    def test_new_intake(self):
        self.as_(self.admin)
        res = self.post("/api/staff/intakes", {"intake": "January 2027 Cohort", "cohortDate": "2027-01-11",
                                               "opens": "2026-12-01", "closes": "2027-01-08"})
        self.assertEqual(res.json()["admissions"]["intake"], "January 2027 Cohort")
        self.assertEqual(Application.objects.get(pk=self.a1.pk).cohort.name, "October 2026 Cohort")  # unchanged
        self.assertEqual(self.post("/api/staff/intakes", {"intake": "january 2027 cohort", "cohortDate": "2027-01-11"}).json()["code"], "invalid")

    def test_notifications(self):
        Notification.objects.create(recipient=self.staff, title="A", body="x")
        Notification.objects.create(recipient=self.staff, title="B", body="y")
        Notification.objects.create(recipient=self.admin, title="C", body="z")
        self.as_(self.staff)
        data = self.client.get("/api/notifications").json()
        self.assertEqual((len(data["results"]), data["unread"]), (2, 2))
        self.assertEqual(self.post(f"/api/notifications/{data['results'][0]['id']}/read").json()["unread"], 1)
        self.assertEqual(self.post("/api/notifications/read-all").json()["unread"], 0)
        self.assertEqual(Notification.objects.filter(recipient=self.admin, read=False).count(), 1)
