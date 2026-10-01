from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User


class ApiFoundationTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)

    def test_health(self):
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")

    def test_unknown_api_path_returns_json_error_shape(self):
        res = self.client.get("/api/does-not-exist")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json(), {"error": "Not found.", "code": "not_found", "fields": {}})

    def test_csrf_endpoint_sets_cookie(self):
        res = self.client.get("/api/auth/csrf")
        self.assertEqual(res.status_code, 200)
        self.assertIn("csrftoken", res.cookies)

    def test_authenticated_unsafe_request_requires_csrf_token(self):
        User.objects.create_user("staff@tsce.edu.ng", "s3cure-pass!", full_name="Staff", role=User.Role.STAFF)
        self.client.login(email="staff@tsce.edu.ng", password="s3cure-pass!")

        res = self.client.post("/api/does-not-exist", {}, format="json")
        self.assertEqual(res.status_code, 403)
        self.assertIn("CSRF", res.json()["error"])

        token = self.client.get("/api/auth/csrf").json()["csrfToken"]
        res = self.client.post("/api/does-not-exist", {}, format="json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(res.status_code, 404)


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
