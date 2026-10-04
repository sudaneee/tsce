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
from apps.programmes.models import Programme

from .models import Application, AwardRequest

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
PDF = b"%PDF-1.4\n% test\n"
OCT_1, SEP_30 = date(2026, 10, 1), date(2026, 9, 30)
PW = "x-Pass-2026!"


def on(day):
    """Freeze 'today' (Lagos) for the admissions rules."""
    return mock.patch("django.utils.timezone.localdate", return_value=day)


@override_settings(CACHES=LOCMEM, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ApiTestCase(TestCase):
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

    def account(self, email="aisha@example.com", role=User.Role.APPLICANT, verified=True, name="Aisha Garba"):
        return User.objects.create_user(email, PW, full_name=name, role=role, phone="0803 123 4567",
                                        email_verified_at=timezone.now() if verified else None)

    def sign_in(self, user):
        self.client.force_login(user)

    def csrf(self):
        return {"HTTP_X_CSRFTOKEN": self.client.get("/api/auth/csrf").json()["csrfToken"]}

    def form(self, **over):
        data = {
            "firstName": "Aisha", "middleName": "", "lastName": "Garba", "gender": "Female", "dob": "2002-05-14",
            "phone": "+234 803 123 4567", "email": "", "address": "12 Samaru Road, Zaria",
            "state": "Kaduna", "lga": "Zaria", "qualification": "OND", "institution": "Nuhu Bamalli Polytechnic",
            "gradYear": "2023", "waecStatus": "Available", "waecYear": "2022", "numAs": "6",
            "programmeId": "fullstack", "schedule": "Weekend (Sat & Sun, 10:00am – 3:00pm)",
            "awardRequest": "none", "declare": "true",
        }
        data.update(over)
        return data

    def apply(self, day=OCT_1, **over):
        with on(day):
            return self.client.post("/api/applications", self.form(**over), format="multipart", **self.csrf())


class SiteEndpointTests(ApiTestCase):
    def test_site_returns_settings_and_active_catalogue(self):
        Programme.objects.filter(slug="cad").update(status=Programme.Status.INACTIVE)
        with on(OCT_1):
            data = self.client.get("/api/site").json()
        self.assertEqual(len(data["programmes"]), 10)
        fs = next(p for p in data["programmes"] if p["id"] == "fullstack")
        self.assertEqual(fs["seats"], {"enrolled": 0, "capacity": 40, "available": 40, "pct": 0})
        adm = data["settings"]["admissions"]
        self.assertEqual((adm["intake"], adm["applicationFee"], adm["open"]), ("October 2026 Cohort", 5000, True))
        self.assertNotIn("scholarshipMax", data["settings"]["discounts"])
        pay = data["settings"]["payments"]
        self.assertEqual((pay["payerCharge"], pay["allowCard"], pay["allowTransfer"]), (300, False, True))

    def test_early_bird_ends_on_the_deadline_day(self):
        with on(SEP_30):
            self.assertTrue(self.client.get("/api/site").json()["settings"]["discounts"]["earlyBirdOpen"])
        with on(OCT_1):
            self.assertFalse(self.client.get("/api/site").json()["settings"]["discounts"]["earlyBirdOpen"])


class CreateApplicationTests(ApiTestCase):
    def test_requires_a_signed_in_verified_applicant_account(self):
        self.assertEqual(self.apply().status_code, 401)
        self.sign_in(self.account(verified=False))
        self.assertEqual(self.apply().json()["code"], "email_unverified")
        self.sign_in(self.account("rabi@tsce.edu.ng", role=User.Role.STAFF, name="Rabi"))
        self.assertEqual(self.apply().json()["code"], "staff_account")
        self.assertEqual(Application.objects.count(), 0)

    def test_self_applicant(self):
        user = self.account()
        self.sign_in(user)
        res = self.apply(email="someone.else@example.com",
                         resultFile=SimpleUploadedFile("waec.pdf", PDF, content_type="application/pdf"))
        self.assertEqual(res.status_code, 201, res.content)
        body = res.json()
        self.assertEqual((body["id"], body["status"], body["applicationFee"], body["applicationFeeDue"]),
                         ("TSCE/APP/2026/00001", "Admitted", 5000, 5000))  # admitted on applying (4 Oct 2026)
        self.assertEqual((body["fee"], body["amountPayable"]), (50000, 55000))  # application fee added
        app = Application.objects.get()
        self.assertEqual(app.email, "aisha@example.com")  # self-applicants always use their account email
        self.assertEqual(app.phone, "0803 123 4567")
        self.assertTrue(app.waec_file.storage.exists(app.waec_file.name))
        self.assertTrue(Notification.objects.filter(recipient=user, title="Admission approved").exists())

    def test_parent_applies_for_several_children(self):
        self.sign_in(self.account("rabi.musa@example.com", role=User.Role.PARENT, name="Rabi Musa"))
        a = self.apply(firstName="Aisha", lastName="Musa", email="aisha.musa@example.com")
        b = self.apply(firstName="Umar", lastName="Musa", gender="Male", dob="2005-01-02", programmeId="network")
        self.assertEqual((a.status_code, b.status_code), (201, 201))
        apps = self.client.get("/api/applications").json()
        self.assertEqual({x["name"] for x in apps}, {"Aisha Musa", "Umar Musa"})
        self.assertEqual(Application.objects.get(first_name="Aisha").email, "aisha.musa@example.com")
        self.assertEqual(Application.objects.get(first_name="Umar").email, "")

        dup = self.apply(firstName="aisha", lastName="MUSA", email="")
        self.assertEqual(dup.json()["code"], "duplicate_application")
        self.assertEqual(dup.json()["extra"]["applicationId"], a.json()["id"])

    def test_field_validation(self):
        self.sign_in(self.account())
        form = self.form(phone="12345", gradYear="2031")
        del form["declare"]
        with on(OCT_1):
            res = self.client.post("/api/applications", form, format="multipart", **self.csrf())
        self.assertEqual(set(res.json()["fields"]), {"phone", "gradYear", "declare"})
        res = self.apply(schedule="Midnight", waecYear="")
        self.assertEqual(set(res.json()["fields"]), {"schedule", "waecYear"})
        self.assertIn("resultFile", self.apply(resultFile=SimpleUploadedFile("w.pdf", b"MZ fake")).json()["fields"])
        self.assertIn("awardRequest", self.apply(awardRequest="scholarship").json()["fields"])  # discontinued

    def test_closed_admissions_and_full_programmes(self):
        self.sign_in(self.account())
        SiteSettings.objects.filter(pk=1).update(accepting_applications=False)
        self.assertEqual(self.apply().json()["code"], "admissions_closed")
        SiteSettings.objects.filter(pk=1).update(accepting_applications=True)
        res = self.apply(day=date(2026, 10, 13))
        self.assertIn("closed on 12 October 2026", res.json()["error"])
        Programme.objects.filter(slug="fullstack").update(capacity=0)
        self.assertEqual(self.apply().json()["code"], "programme_full")

    def test_excellence_award_request(self):
        self.sign_in(self.account())
        self.assertEqual(self.apply(awardRequest="excellence", waecYear="2018").json()["code"], "not_eligible")
        res = self.apply(awardRequest="excellence")
        self.assertEqual((res.status_code, res.json()["status"]), (201, "Awaiting Verification"))
        award = AwardRequest.objects.get()
        self.assertEqual((award.type, award.requested_pct, award.status), ("excellence", 50, "Pending"))


class ApplicationVisibilityTests(ApiTestCase):
    def test_owner_and_staff_only(self):
        self.sign_in(self.account())
        number = self.apply().json()["id"]
        url = f"/api/applications/{number}"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.sign_in(self.account("x@example.com", name="X"))
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get("/api/applications").json(), [])
        self.sign_in(self.account("rabi@tsce.edu.ng", role=User.Role.STAFF, name="Rabi"))
        self.assertEqual(self.client.get(url).status_code, 200)


class PublicCommsTests(ApiTestCase):
    def test_enquiry(self):
        res = self.client.post("/api/enquiries", {"name": "Musa", "email": "musa@example.com", "phone": "08061234567",
                                                  "message": "When does the next cohort start?"}, format="json", **self.csrf())
        self.assertEqual(res.status_code, 201)
        self.assertEqual(Enquiry.objects.get().phone, "0806 123 4567")

    def test_public_announcements_only_published_public(self):
        Announcement.objects.create(title="Open day", body="Visit us", audience="Public", status="Published",
                                    published_at=timezone.now())
        Announcement.objects.create(title="Draft", body="x", audience="Public", status="Draft")
        Announcement.objects.create(title="Staff only", body="x", audience="Staff", status="Published")
        self.assertEqual([a["title"] for a in self.client.get("/api/announcements/public").json()], ["Open day"])

    def test_certificate_verification(self):
        user = self.account()
        self.sign_in(user)
        self.apply()
        app = Application.objects.get()
        student = Student.objects.create(user=user, student_no="TSCE/2026/00001", first_name="Aisha",
                                         last_name="Garba", gender="Female", phone=app.phone)
        enrollment = Enrollment.objects.create(student=student, application=app, programme=app.programme,
                                               cohort=app.cohort, schedule=app.schedule, start_date=OCT_1,
                                               end_date=OCT_1 + timedelta(days=60))
        cert = Certificate.objects.create(number="TSCE/CERT/2026/00001", enrollment=enrollment, issued_at=timezone.now())
        verify = lambda no: self.client.get("/api/certificates/verify", {"no": no}).json()  # noqa: E731
        self.assertEqual(verify("tsce/cert/2026/00001")["holder"], "Aisha Garba")
        self.assertEqual(verify("TSCE/CERT/2026/99999")["status"], "not_found")
        cert.status = Certificate.Status.REVOKED
        cert.save()
        self.assertEqual(verify("TSCE/CERT/2026/00001")["status"], "revoked")
