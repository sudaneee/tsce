import shutil
import tempfile
from datetime import date, timedelta
from io import StringIO
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.academics.models import Certificate, Enrollment, Student
from apps.accounts.models import User
from apps.comms.models import Announcement, Enquiry, Notification
from apps.core.models import SiteSettings
from apps.programmes.models import Cohort, Programme

from .models import Application, AwardRequest

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
PDF = b"%PDF-1.4\n% test\n"
OCT_1, SEP_30 = date(2026, 10, 1), date(2026, 9, 30)


def on(day):
    """Freeze 'today' (Lagos) for the admissions rules."""
    return mock.patch("django.utils.timezone.localdate", return_value=day)


@override_settings(CACHES=LOCMEM)
class PublicApiTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_school", stdout=StringIO())

    def setUp(self):
        cache.clear()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        override = override_settings(PRIVATE_MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)
        self.client = APIClient(enforce_csrf_checks=True)

    def csrf(self):
        return {"HTTP_X_CSRFTOKEN": self.client.get("/api/auth/csrf").json()["csrfToken"]}

    def form(self, **over):
        data = {
            "firstName": "Aisha", "middleName": "", "lastName": "Garba", "gender": "Female", "dob": "2002-05-14",
            "phone": "+234 803 123 4567", "email": "Aisha.Garba@example.com", "address": "12 Samaru Road, Zaria",
            "state": "Kaduna", "lga": "Zaria", "qualification": "OND", "institution": "Nuhu Bamalli Polytechnic",
            "gradYear": "2023", "waecStatus": "Available", "waecYear": "2022", "numAs": "6",
            "programmeId": "fullstack", "schedule": "Weekend (Sat & Sun, 10:00am – 3:00pm)",
            "awardRequest": "none", "password": "Zaria-Campus-2026", "declare": "on",
        }
        data.update(over)
        return data

    def apply(self, day=OCT_1, **over):
        with on(day):
            return self.client.post("/api/applications", self.form(**over), format="multipart", **self.csrf())


class SiteEndpointTests(PublicApiTestCase):
    def test_site_returns_settings_and_active_catalogue(self):
        Programme.objects.filter(slug="cad").update(status=Programme.Status.INACTIVE)
        with on(OCT_1):
            data = self.client.get("/api/site").json()
        self.assertEqual(len(data["programmes"]), 10)  # inactive hidden from visitors
        fs = next(p for p in data["programmes"] if p["id"] == "fullstack")
        self.assertEqual(len(fs["modules"]), 11)
        self.assertEqual(fs["seats"], {"enrolled": 0, "capacity": 40, "available": 40, "pct": 0})
        self.assertIsNone(fs["instructor"])
        adm = data["settings"]["admissions"]
        self.assertEqual((adm["intake"], adm["cohortDate"], adm["open"]), ("October 2026 Cohort", "2026-10-12", True))

    def test_early_bird_ends_on_the_deadline_day(self):
        with on(SEP_30):
            self.assertTrue(self.client.get("/api/site").json()["settings"]["discounts"]["earlyBirdOpen"])
        with on(OCT_1):
            self.assertFalse(self.client.get("/api/site").json()["settings"]["discounts"]["earlyBirdOpen"])


class CreateApplicationTests(PublicApiTestCase):
    def test_happy_path_creates_account_signs_in_and_notifies(self):
        staff = User.objects.create_user("rabi@tsce.edu.ng", "x-Pass-2026!", full_name="Rabi", role=User.Role.STAFF)
        res = self.apply(resultFile=SimpleUploadedFile("waec.pdf", PDF, content_type="application/pdf"))
        self.assertEqual(res.status_code, 201, res.content)
        app_json = res.json()["application"]
        self.assertEqual(app_json["id"], "TSCE/APP/2026/00001")
        self.assertEqual((app_json["fee"], app_json["discountAmount"], app_json["amountPayable"]), (50000, 0, 50000))
        self.assertEqual((app_json["status"], app_json["paymentStatus"]), ("Pending", "Unpaid"))

        app = Application.objects.get()
        self.assertEqual(app.email, "aisha.garba@example.com")
        self.assertEqual(app.phone, "0803 123 4567")
        self.assertTrue(app.waec_file.name.startswith("waec/"))
        self.assertTrue(app.waec_file.storage.exists(app.waec_file.name))
        self.assertEqual(app.user.role, User.Role.APPLICANT)
        self.assertEqual(self.client.get("/api/auth/me").json()["user"]["applicationId"], app.number)  # signed in
        self.assertEqual(app.events.first().text, "Application submitted online")
        self.assertTrue(Notification.objects.filter(recipient=app.user, title="Application received").exists())
        self.assertTrue(Notification.objects.filter(recipient=staff, title="New application").exists())

    def test_early_bird_discount_before_deadline(self):
        # The flyer opens enrolment on 1 Oct, the same day early bird ends, so
        # open it earlier here (TSCE must confirm the real dates).
        Cohort.objects.update(enrolment_opens=date(2026, 9, 1))
        res = self.apply(day=SEP_30)
        self.assertEqual(res.json()["application"]["amountPayable"], 42500)
        self.assertEqual(res.json()["application"]["discountType"], "earlybird")

    def test_requires_csrf(self):
        with on(OCT_1):
            res = self.client.post("/api/applications", self.form(), format="multipart")
        self.assertEqual(res.status_code, 403)

    def test_field_validation(self):
        # Stage 1: per-field checks (an unchecked checkbox is simply absent from the form)
        form = self.form(phone="12345", gradYear="2031")
        del form["declare"]
        with on(OCT_1):
            res = self.client.post("/api/applications", form, format="multipart", **self.csrf())
        self.assertEqual(set(res.json()["fields"]), {"phone", "gradYear", "declare"})
        # Stage 2: cross-field checks once every field is individually valid
        res = self.apply(schedule="Midnight", password="password", waecYear="")
        self.assertEqual(set(res.json()["fields"]), {"schedule", "password", "waecYear"})
        self.assertEqual(Application.objects.count(), 0)
        self.assertEqual(User.objects.count(), 0)

    def test_rejects_fake_documents(self):
        fake = SimpleUploadedFile("waec.pdf", b"MZ\x90\x00 not a pdf", content_type="application/pdf")
        self.assertIn("resultFile", self.apply(resultFile=fake).json()["fields"])
        exe = SimpleUploadedFile("waec.exe", PDF)
        self.assertIn("resultFile", self.apply(resultFile=exe).json()["fields"])

    def test_closed_admissions(self):
        SiteSettings.objects.filter(pk=1).update(accepting_applications=False)
        res = self.apply()
        self.assertEqual((res.status_code, res.json()["code"]), (400, "admissions_closed"))
        with on(date(2026, 10, 13)):  # after enrolment closes (12 Oct)
            SiteSettings.objects.filter(pk=1).update(accepting_applications=True)
            res = self.client.post("/api/applications", self.form(), format="multipart", **self.csrf())
        self.assertEqual(res.json()["code"], "admissions_closed")
        self.assertIn("closed on 12 October 2026", res.json()["error"])

    def test_full_programme(self):
        self.assertEqual(self.apply().status_code, 201)
        Application.objects.update(payment_status=Application.PaymentStatus.PAID)
        Programme.objects.filter(slug="fullstack").update(capacity=1)
        self.client.post("/api/auth/logout", **self.csrf())
        res = self.apply(email="other@example.com")
        self.assertEqual((res.json()["code"], list(res.json()["fields"])), ("programme_full", ["programmeId"]))

    def test_existing_account_needs_its_password_and_no_duplicates(self):
        self.assertEqual(self.apply().status_code, 201)
        self.client.post("/api/auth/logout", **self.csrf())

        wrong = self.apply(password="Not-The-Same-99")
        self.assertEqual((wrong.json()["code"], list(wrong.json()["fields"])), ("account_exists", ["password"]))

        dup = self.apply()
        self.assertEqual(dup.json()["code"], "duplicate_application")
        self.assertEqual(dup.json()["extra"]["applicationId"], "TSCE/APP/2026/00001")

        second = self.apply(programmeId="cad", schedule="Weekend (Sat & Sun, 10:00am – 3:00pm)")
        self.assertEqual(second.status_code, 201)
        self.assertEqual(User.objects.count(), 1)

        # Now signed in: a third application needs no password at all
        third = self.apply(programmeId="network", password="")
        self.assertEqual(third.status_code, 201, third.content)

    def test_visitors_must_set_a_password(self):
        self.assertEqual(list(self.apply(password="").json()["fields"]), ["password"])

    def test_signed_in_user_must_apply_with_own_email_and_staff_cannot_apply(self):
        self.assertEqual(self.apply().status_code, 201)
        res = self.apply(email="someone.else@example.com", programmeId="cad")
        self.assertEqual(res.json()["code"], "email_mismatch")
        User.objects.create_user("rabi@tsce.edu.ng", "x-Pass-2026!", full_name="Rabi", role=User.Role.STAFF)
        self.client.post("/api/auth/logout", **self.csrf())
        self.assertEqual(self.apply(email="rabi@tsce.edu.ng", password="x-Pass-2026!").json()["code"], "staff_account")

    def test_award_requests(self):
        res = self.apply(awardRequest="excellence", waecYear="2018")
        self.assertEqual(res.json()["code"], "not_eligible")
        res = self.apply(awardRequest="excellence")
        self.assertEqual(res.status_code, 201)
        award = AwardRequest.objects.get()
        self.assertEqual((award.type, award.requested_pct, award.status), ("excellence", 50, "Pending"))
        self.assertEqual(res.json()["application"]["awardRequest"]["status"], "Pending")


class ApplicationDetailTests(PublicApiTestCase):
    def test_owner_and_staff_only(self):
        self.apply()
        url = "/api/applications/TSCE/APP/2026/00001"
        self.assertEqual(self.client.get(url).json()["programmeId"], "fullstack")
        self.client.post("/api/auth/logout", **self.csrf())
        self.assertEqual(self.client.get(url).status_code, 401)

        User.objects.create_user("x@example.com", "x-Pass-2026!", full_name="X", role=User.Role.APPLICANT)
        self.client.login(email="x@example.com", password="x-Pass-2026!")
        self.assertEqual(self.client.get(url).status_code, 404)

        User.objects.create_user("rabi@tsce.edu.ng", "x-Pass-2026!", full_name="Rabi", role=User.Role.STAFF)
        self.client.login(email="rabi@tsce.edu.ng", password="x-Pass-2026!")
        self.assertEqual(self.client.get(url).status_code, 200)


class PublicCommsTests(PublicApiTestCase):
    def test_enquiry(self):
        res = self.client.post("/api/enquiries", {"name": "Musa", "email": "musa@example.com", "phone": "08061234567",
                                                  "message": "When does the next cohort start?"}, format="json", **self.csrf())
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Enquiry.objects.get().phone, "0806 123 4567")
        bad = self.client.post("/api/enquiries", {"name": "M", "email": "nope", "message": "hi"}, format="json", **self.csrf())
        self.assertEqual(set(bad.json()["fields"]), {"email", "message"})

    def test_public_announcements_only_published_public(self):
        Announcement.objects.create(title="Open day", body="Visit us", audience="Public", status="Published",
                                    published_at=timezone.now())
        Announcement.objects.create(title="Draft", body="x", audience="Public", status="Draft")
        Announcement.objects.create(title="Staff only", body="x", audience="Staff", status="Published")
        self.assertEqual([a["title"] for a in self.client.get("/api/announcements/public").json()], ["Open day"])

    def test_certificate_verification(self):
        self.apply()
        app = Application.objects.get()
        student = Student.objects.create(user=app.user, student_no="TSCE/2026/00001", first_name="Aisha",
                                         last_name="Garba", gender="Female", phone=app.phone)
        enrollment = Enrollment.objects.create(student=student, application=app, programme=app.programme,
                                               cohort=app.cohort, schedule=app.schedule, start_date=OCT_1,
                                               end_date=OCT_1 + timedelta(days=60))
        cert = Certificate.objects.create(number="TSCE/CERT/2026/00001", enrollment=enrollment, issued_at=timezone.now())
        verify = lambda no: self.client.get("/api/certificates/verify", {"no": no}).json()  # noqa: E731
        ok = verify("tsce/cert/2026/00001")
        self.assertEqual((ok["status"], ok["holder"], ok["programme"]), ("valid", "Aisha Garba", "Full-Stack Software Engineering"))
        self.assertEqual(verify("TSCE/CERT/2026/99999")["status"], "not_found")
        cert.status = Certificate.Status.REVOKED
        cert.save()
        self.assertEqual(verify("TSCE/CERT/2026/00001"), {"status": "revoked", "number": "TSCE/CERT/2026/00001"})
