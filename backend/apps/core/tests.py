from io import StringIO

from django.core.management import call_command
from django.test import Client, TestCase

from apps.accounts.models import User


class FoundationTests(TestCase):
    def test_health(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")

    def test_only_zainpay_and_health_remain_under_api(self):
        res = self.client.get("/api/does-not-exist")
        self.assertEqual((res.status_code, res.json()["code"]), (404, "not_found"))
        for gone in ("/api/site", "/api/auth/me", "/api/applications", "/api/staff/summary", "/api/payments/initialize"):
            self.assertEqual(self.client.get(gone).status_code, 404, gone)

    def test_forms_require_a_csrf_token(self):
        call_command("seed_school", stdout=StringIO())
        User.objects.create_user("staff@tsce.edu.ng", "s3cure-pass!", full_name="Staff", role=User.Role.STAFF)
        strict = Client(enforce_csrf_checks=True)
        strict.login(email="staff@tsce.edu.ng", password="s3cure-pass!")
        self.assertEqual(strict.post("/staff/notifications/", {}).status_code, 403)
        page = strict.get("/staff/notifications/")
        token = page.cookies["csrftoken"].value
        self.assertEqual(strict.post("/staff/notifications/", {"csrfmiddlewaretoken": token}).status_code, 302)


class UserModelTests(TestCase):
    def test_email_is_normalised_and_login_is_case_insensitive(self):
        user = User.objects.create_user("  Amina.Yusuf@Example.COM ", "s3cure-pass!", full_name="Amina Yusuf")
        self.assertEqual(user.email, "amina.yusuf@example.com")
        self.assertEqual(user.role, User.Role.APPLICANT)
        self.assertTrue(self.client.login(email="AMINA.YUSUF@example.com", password="s3cure-pass!"))

    def test_superuser_is_admin_role(self):
        admin = User.objects.create_superuser("admin@tsce.edu.ng", "s3cure-pass!", full_name="Admin")
        self.assertEqual(admin.role, User.Role.ADMIN)
        self.assertTrue(admin.is_portal_staff and admin.is_staff and admin.is_superuser)
