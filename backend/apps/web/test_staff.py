"""Server-rendered staff portal: access, pages, and every action."""
from datetime import date

from django.utils import timezone

from apps.accounts.models import StaffProfile, User
from apps.admissions.models import Application, AwardRequest
from apps.comms.models import Notification
from apps.core.models import SiteSettings
from apps.payments.models import Payment
from apps.programmes.models import Cohort

from .tests import PW, WebTestCase


class StaffTestCase(WebTestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user("director@tsce.edu.ng", PW, full_name="Test Director", role="admin",
                                              email_verified_at=timezone.now())
        self.rabi = User.objects.create_user("rabi@tsce.edu.ng", PW, full_name="Rabi Isa", role="staff",
                                             email_verified_at=timezone.now())
        self.parent = self.account("musa@example.com", role="parent", name="Musa Bello")
        self.app = self.make_app(self.parent, first_name="Umar", status="Awaiting Verification",
                                 waec_status="Available", waec_year=2024, num_as=7)
        AwardRequest.objects.create(application=self.app, type="excellence", requested_pct=50, evidence="WAEC 2024 — 7 A's")
        self.client.force_login(self.rabi)

    def paid(self, app, ref, amount, minutes=0, **extra):
        return Payment.objects.create(reference=ref, application=app, user=app.user, name=app.full_name, email=app.user.email,
                                      description="x", amount=amount, gateway="zainpay", status="SUCCESS",
                                      verified_at=timezone.now() + timezone.timedelta(minutes=minutes), **extra)


class AccessTests(StaffTestCase):
    def test_who_gets_in(self):
        self.client.logout()
        self.assertEqual(self.client.get("/staff/")["Location"], "/account/login/?role=staff&next=%2Fstaff%2F")
        self.client.force_login(self.parent)
        self.assertEqual(self.client.get("/staff/")["Location"], "/my-applications/")
        self.client.force_login(self.rabi)
        self.assertEqual(self.client.get("/staff/").status_code, 200)
        self.assertEqual(self.client.get("/staff/settings/").status_code, 403)   # admin only
        self.assertEqual(self.client.get("/staff/team/").status_code, 403)
        self.assertNotContains(self.client.get("/staff/"), "/staff/settings/")
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/staff/settings/").status_code, 200)

    def test_staff_sign_in_lands_on_the_dashboard(self):
        self.client.logout()
        res = self.client.post("/account/login/?role=staff", {"email": "rabi@tsce.edu.ng", "password": PW})
        self.assertEqual(res["Location"], "/staff/")

    def test_old_staff_addresses_redirect(self):
        cases = {"/pages/staff/dashboard.html": "/staff/", "/pages/staff/scholarships.html": "/staff/awards/",
                 "/pages/staff/applications.html?status=Admitted": "/staff/applications/?status=Admitted",
                 f"/pages/staff/applications.html?id={self.app.number}": f"/staff/applications/{self.app.number}/",
                 "/pages/staff/payments.html?ref=TSCE-ZP-1": "/staff/payments/TSCE-ZP-1/",
                 "/pages/staff/staff.html": "/staff/team/", "/pages/staff/settings.html": "/staff/settings/"}
        for old, new in cases.items():
            self.assertEqual(self.client.get(old)["Location"], new, old)


class DashboardAndListTests(StaffTestCase):
    def test_dashboard_numbers_and_badges(self):
        page = self.client.get("/staff/")
        self.assertContains(page, "Awards to verify")
        self.assertContains(page, 'data-count-for="staff-scholarships">1<')
        self.assertContains(page, "Umar Garba")

    def test_applications_filters_and_csv(self):
        self.make_app(self.account("a@example.com", name="Aisha Garba"), number="TSCE/APP/2026/00002", status="Admitted")
        page = self.client.get("/staff/applications/")
        self.assertContains(page, "TSCE/APP/2026/00002")
        self.assertContains(page, "Awaiting Verification <b>1</b>")
        page = self.client.get("/staff/applications/?status=Admitted")
        self.assertContains(page, "TSCE/APP/2026/00002")
        self.assertNotContains(page, ">TSCE/APP/2026/00001<")
        self.assertContains(self.client.get("/staff/applications/?q=umar"), ">TSCE/APP/2026/00001<")
        csv = self.client.get("/staff/applications/?export=csv")
        self.assertEqual(csv["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("TSCE/APP/2026/00002", csv.content.decode("utf-8"))

    def test_awards_queue(self):
        page = self.client.get("/staff/awards/")
        self.assertContains(page, "To verify (1)")
        self.assertContains(page, "WAEC 2024")
        self.assertContains(self.client.get("/staff/awards/?tab=Approved"), "Approved (0)")


class ApplicationActionTests(StaffTestCase):
    def url(self):
        return f"/staff/applications/{self.app.number}/"

    def test_detail_shows_everything(self):
        page = self.client.get(self.url())
        for text in ("Excellence Award to verify", "Approve award (50%)", "Musa Bello", "Parent / guardian account", "Activity"):
            self.assertContains(page, text)

    def test_approve_award(self):
        res = self.client.post(self.url(), {"action": "award-yes", "note": "Original WAEC seen"})
        self.assertEqual(res["Location"], self.url())
        self.app.refresh_from_db()
        self.assertEqual((self.app.status, self.app.amount_payable), ("Admitted", 30000))
        self.assertContains(self.client.get(self.url()), "Excellence Award approved")

    def test_decline_award_then_remind_then_reject(self):
        self.client.post(self.url(), {"action": "award-no"})
        self.app.refresh_from_db()
        self.assertEqual((self.app.status, self.app.amount_payable), ("Admitted", 55000))
        self.client.post(self.url(), {"action": "remind"})
        self.assertTrue(Notification.objects.filter(recipient=self.parent, title__startswith="Reminder").exists())
        self.client.post(self.url(), {"action": "reject", "note": "Incomplete details"})
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, "Rejected")
        page = self.client.get(self.url())
        self.assertNotContains(page, 'value="reject"')

    def test_service_errors_are_shown(self):
        Application.objects.filter(pk=self.app.pk).update(status="Admitted")
        res = self.client.post(self.url(), {"action": "award-yes"}, follow=True)
        self.assertContains(res, "isn&#x27;t waiting for award verification")

    def test_waec_file_is_staff_only(self):
        self.assertEqual(self.client.get(f"/staff/waec/{self.app.number}/").status_code, 404)  # none uploaded
        self.client.force_login(self.parent)
        self.assertEqual(self.client.get(f"/staff/waec/{self.app.number}/")["Location"], "/my-applications/")


class PaymentPageTests(StaffTestCase):
    def setUp(self):
        super().setUp()
        Application.objects.filter(pk=self.app.pk).update(status="Enrolled", payment_status="Paid", amount_paid=55000)
        self.first = self.paid(self.app, "TSCE-ZP-20261001-000011", 55000, purpose="programme_fee")
        self.dup = self.paid(self.app, "TSCE-ZP-20261001-000012", 55000, minutes=3, purpose="programme_fee")

    def test_list_kpis_duplicates_and_csv(self):
        page = self.client.get("/staff/payments/")
        self.assertContains(page, "Duplicates to refund")
        self.assertContains(page, "TSCE-ZP-20261001-000012</a> <span class=\"badge badge-danger no-dot\">Duplicate")
        dups = self.client.get("/staff/payments/?dup=1")
        self.assertNotContains(dups, "TSCE-ZP-20261001-000011<")
        self.assertIn("TSCE-ZP-20261001-000012", self.client.get("/staff/payments/?export=csv").content.decode())

    def test_refund_a_duplicate(self):
        url = f"/staff/payments/{self.dup.reference}/"
        self.assertContains(self.client.get(url), "Record refund")
        self.assertContains(self.client.post(url, {"action": "refund", "transferRef": ""}), "This field is required")
        res = self.client.post(url, {"action": "refund", "transferRef": "GTB-123", "note": "two tabs"})
        self.assertEqual(res["Location"], url)
        self.dup.refresh_from_db()
        self.assertEqual(self.dup.status, "REFUNDED")
        self.assertTrue(Payment.objects.filter(reference=f"{self.dup.reference}-RF", gateway_ref="GTB-123").exists())

    def test_a_counted_payment_cant_be_refunded(self):
        res = self.client.post(f"/staff/payments/{self.first.reference}/", {"action": "refund", "transferRef": "X"}, follow=True)
        self.assertContains(res, "Only duplicate payments can be refunded")

    def test_receipt_and_zainpay_check(self):
        self.assertContains(self.client.get(f"/staff/payments/{self.first.reference}/receipt/"), "PAID · VERIFIED")
        pending = Payment.objects.create(reference="TSCE-ZP-20261001-000013", application=self.app, user=self.parent, name="x",
                                         email="x@example.com", description="x", amount=1, gateway="simulator",
                                         gateway_payload={"simulator": {"outcome": "success"}})
        res = self.client.post(f"/staff/payments/{pending.reference}/", {"action": "check"}, follow=True)
        self.assertContains(res, "Checked with Zainpay — status: SUCCESS")


class TeamTests(StaffTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_add_with_login_shows_temporary_password(self):
        res = self.client.post("/staff/team/new/", {"fullName": "Kamal Shehu", "title": "Bursar", "email": "Bursary@tsce.edu.ng",
                                                    "phone": "0803 111 2222", "department": "Finance", "access": "staff"})
        self.assertContains(res, "Temporary password")
        user = User.objects.get(email="bursary@tsce.edu.ng")
        self.assertTrue(user.must_change_password)
        self.assertTrue(user.check_password(res.context["password"]))

    def test_instructor_without_login(self):
        res = self.client.post("/staff/team/new/", {"fullName": "Engr. Musa Garba", "title": "Instructor", "department": "Academics",
                                                    "access": "none"})
        self.assertEqual(res["Location"], "/staff/team/")
        self.assertContains(self.client.get("/staff/team/"), "No login")
        self.assertIsNone(StaffProfile.objects.get(full_name="Engr. Musa Garba").user)

    def test_validation_and_self_protection(self):
        res = self.client.post("/staff/team/new/", {"fullName": "X", "title": "Y", "department": "Finance", "access": "staff"})
        self.assertContains(res, "An email address is needed for portal access")
        self.client.get("/staff/team/")  # creates profiles for existing staff logins
        me = StaffProfile.objects.get(user=self.admin)
        page = self.client.get(f"/staff/team/{me.pk}/")
        self.assertContains(page, "You can't change your own access or status")
        self.assertNotContains(page, 'value="reset"')

    def test_reset_password(self):
        self.client.get("/staff/team/")
        rabi = StaffProfile.objects.get(user=self.rabi)
        res = self.client.post(f"/staff/team/{rabi.pk}/", {"action": "reset"})
        self.assertContains(res, "Temporary password")
        self.rabi.refresh_from_db()
        self.assertTrue(self.rabi.must_change_password)
        self.assertTrue(self.rabi.check_password(res.context["password"]))


class SettingsTests(StaffTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_save_sections(self):
        res = self.client.post("/staff/settings/", {"section": "admissions", "admissions-intake": "October 2026 Cohort",
                                                    "admissions-opens": "2026-09-01", "admissions-closes": "2026-10-19",
                                                    "admissions-cohortDate": "2026-10-19", "admissions-earlyBirdDeadline": "2026-10-19",
                                                    "admissions-applicationFee": "6000", "admissions-acceptingApplications": "on"})
        self.assertEqual(res["Location"], "/staff/settings/#admissions")
        s = SiteSettings.load()
        self.assertEqual((s.application_fee, s.accepting_applications, s.allow_installments), (6000, True, False))
        self.assertEqual(s.current_cohort.enrolment_closes, date(2026, 10, 19))
        self.client.post("/staff/settings/", {"section": "institution", "institution-name": "Trust Skill Acquisition Centre of Excellence",
                                              "institution-short": "TSCE", "institution-address": "KM8, Sokoto Road",
                                              "institution-phones": "0803 452 2501, 0904 439 2228", "institution-directorName": "Dr. A. B."})
        s = SiteSettings.load()
        self.assertEqual((s.director_name, s.phones), ("Dr. A. B.", ["0803 452 2501", "0904 439 2228"]))

    def test_validation_errors_stay_on_the_page(self):
        res = self.client.post("/staff/settings/", {"section": "admissions", "admissions-intake": "X", "admissions-cohortDate": "2026-10-01",
                                                    "admissions-opens": "2026-10-10", "admissions-closes": "2026-10-05",
                                                    "admissions-applicationFee": "5000"})
        self.assertContains(res, "The closing date must be after the opening date")

    def test_new_intake(self):
        self.client.post("/staff/settings/", {"section": "intake", "intake-intake": "January 2027 Cohort", "intake-cohortDate": "2027-01-11"})
        self.assertEqual(SiteSettings.load().current_cohort.name, "January 2027 Cohort")
        res = self.client.post("/staff/settings/", {"section": "intake", "intake-intake": "january 2027 cohort", "intake-cohortDate": "2027-01-11"})
        self.assertContains(res, "already exists")
        self.assertEqual(Cohort.objects.count(), 2)


class NotificationAndSearchTests(StaffTestCase):
    def test_bell_open_and_read_all(self):
        n = Notification.objects.create(recipient=self.rabi, title="Duplicate payment — refund needed", body="x",
                                        link=f"pages/staff/applications.html?id={self.app.number}")
        Notification.objects.create(recipient=self.rabi, title="New application", body="y")
        page = self.client.get("/staff/")
        self.assertContains(page, 'id="bellCount">2<')
        res = self.client.post(f"/staff/notifications/{n.pk}/")
        self.assertEqual(res["Location"], f"/pages/staff/applications.html?id={self.app.number}")  # → redirects again to the page
        n.refresh_from_db()
        self.assertTrue(n.read)
        self.client.post("/staff/notifications/", {"next": "/staff/"})
        self.assertEqual(Notification.objects.filter(recipient=self.rabi, read=False).count(), 0)

    def test_search(self):
        self.paid(self.app, "TSCE-ZP-20261001-000077", 100, purpose="programme_fee")
        page = self.client.get("/staff/search/?q=umar")
        self.assertContains(page, self.app.number)
        self.assertContains(self.client.get("/staff/search/?q=000077"), "TSCE-ZP-20261001-000077")
        self.assertContains(self.client.get("/staff/search/?q=u"), "at least 2 characters")


class FileAndDeactivationTests(StaffTestCase):
    def test_uploaded_waec_result_is_served_to_staff_only(self):
        from django.core.files.base import ContentFile

        self.app.waec_file.save("waec.pdf", ContentFile(b"%PDF-1.4\n% test\n"))
        res = self.client.get(f"/staff/waec/{self.app.number}/")
        self.assertEqual((res.status_code, res["Content-Type"]), (200, "application/pdf"))
        self.assertIn("WAEC-TSCE-APP-2026-00001.pdf", res["Content-Disposition"])
        self.assertContains(self.client.get(f"/staff/applications/{self.app.number}/"), "Open uploaded result")
        self.client.force_login(self.parent)
        self.assertEqual(self.client.get(f"/staff/waec/{self.app.number}/").status_code, 302)

    def test_deactivated_staff_cant_sign_in(self):
        self.client.force_login(self.admin)
        self.client.get("/staff/team/")  # creates profiles for existing logins
        rabi = StaffProfile.objects.get(user=self.rabi)
        self.client.post(f"/staff/team/{rabi.pk}/", {"fullName": "Rabi Isa", "title": "Staff", "department": "Admissions",
                                                    "access": "staff", "status": "Inactive", "action": "save"})
        self.rabi.refresh_from_db()
        self.assertFalse(self.rabi.is_active)
        self.client.logout()
        self.assertContains(self.client.post("/account/login/", {"email": "rabi@tsce.edu.ng", "password": PW}),
                            "This account has been disabled")


class AccountPasswordResetTests(StaffTestCase):
    def test_admin_resets_an_applicants_password_from_the_application(self):
        url = f"/staff/applications/{self.app.number}/"
        self.assertNotContains(self.client.get(url), 'value="reset-password"')  # staff (non-admin) don't see it
        self.assertEqual(self.client.post(url, {"action": "reset-password"}).status_code, 403)
        self.client.force_login(self.admin)
        res = self.client.post(url, {"action": "reset-password"})
        self.assertContains(res, "Temporary password")
        self.assertContains(res, f'href="{url}"')  # Done → back to the application
        self.parent.refresh_from_db()
        self.assertTrue(self.parent.must_change_password)
        self.assertTrue(self.parent.check_password(res.context["password"]))
