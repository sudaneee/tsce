from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .models import StaffProfile, User

PW = "Zaria-Campus-2026"
LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(CACHES=LOCMEM)
class AuthTestCase(TestCase):
    def setUp(self):
        cache.clear()  # login throttle counters
        self.client = APIClient(enforce_csrf_checks=True)

    def csrf(self):
        return {"HTTP_X_CSRFTOKEN": self.client.get("/api/auth/csrf").json()["csrfToken"]}

    def login(self, email, password=PW, **extra):
        return self.client.post("/api/auth/login", {"email": email, "password": password, **extra}, format="json", **self.csrf())

    def make(self, email, role, **extra):
        return User.objects.create_user(email, PW, full_name=email.split("@")[0].title(), role=role, **extra)


class LoginTests(AuthTestCase):
    def test_login_returns_session_payload_and_me_matches(self):
        user = self.make("rabi@tsce.edu.ng", User.Role.STAFF)
        StaffProfile.objects.create(user=user, staff_no="STF-002", full_name="Rabi", title="Admissions Officer",
                                    department="Admissions")
        res = self.login("RABI@tsce.edu.ng")
        self.assertEqual(res.status_code, 200)
        payload = res.json()["user"]
        self.assertEqual(payload["email"], "rabi@tsce.edu.ng")
        self.assertEqual((payload["role"], payload["staffId"], payload["isAdmin"]), ("staff", "STF-002", False))
        self.assertEqual(self.client.get("/api/auth/me").json()["user"], payload)

    def test_me_for_visitor_is_null_not_401(self):
        res = self.client.get("/api/auth/me")
        self.assertEqual((res.status_code, res.json()), (200, {"user": None}))

    def test_wrong_password_and_unknown_email_get_the_same_answer(self):
        self.make("amina@example.com", User.Role.STUDENT)
        wrong_pw, unknown = self.login("amina@example.com", "nope-nope-1"), self.login("ghost@example.com")
        self.assertEqual(wrong_pw.status_code, 400)
        self.assertEqual(wrong_pw.json(), unknown.json())
        self.assertEqual(wrong_pw.json()["code"], "invalid_credentials")

    def test_disabled_account_is_explained_only_with_the_right_password(self):
        self.make("old@example.com", User.Role.STUDENT, is_active=False)
        self.assertEqual(self.login("old@example.com").json()["code"], "account_disabled")
        self.assertEqual(self.login("old@example.com", "wrong-pw-123").json()["code"], "invalid_credentials")

    def test_login_requires_csrf_token(self):
        self.make("amina@example.com", User.Role.STUDENT)
        res = self.client.post("/api/auth/login", {"email": "amina@example.com", "password": PW}, format="json")
        self.assertEqual(res.status_code, 403)

    def test_remember_me_off_ends_session_with_browser(self):
        self.make("amina@example.com", User.Role.STUDENT)
        self.login("amina@example.com", remember=False)
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_logout(self):
        self.make("amina@example.com", User.Role.STUDENT)
        self.login("amina@example.com")
        self.assertEqual(self.client.post("/api/auth/logout", **self.csrf()).status_code, 204)
        self.assertIsNone(self.client.get("/api/auth/me").json()["user"])

    def test_login_is_rate_limited(self):
        for _ in range(10):
            self.login("ghost@example.com")
        res = self.login("ghost@example.com")
        self.assertEqual(res.status_code, 429)
        self.assertEqual(res.json()["code"], "throttled")


class ChangePasswordTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make("amina@example.com", User.Role.STUDENT, must_change_password=True)

    def change(self, current, new):
        return self.client.post("/api/auth/change-password", {"currentPassword": current, "newPassword": new},
                                format="json", **self.csrf())

    def test_requires_sign_in_with_401(self):
        self.assertEqual(self.change(PW, "Another-Pass-99").status_code, 401)

    def test_validates_current_and_new_password(self):
        self.login("amina@example.com")
        self.assertIn("currentPassword", self.change("wrong-password", "Another-Pass-99").json()["fields"])
        self.assertIn("newPassword", self.change(PW, "password").json()["fields"])
        self.assertIn("newPassword", self.change(PW, PW).json()["fields"])

    def test_success_keeps_session_and_clears_forced_change(self):
        self.login("amina@example.com")
        res = self.change(PW, "Another-Pass-99")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["user"]["mustChangePassword"])
        self.assertIsNotNone(self.client.get("/api/auth/me").json()["user"])  # still signed in
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Another-Pass-99"))


class AdminResetPasswordTests(AuthTestCase):
    def setUp(self):
        super().setUp()
        self.student = self.make("amina@example.com", User.Role.STUDENT)
        self.staff = self.make("rabi@tsce.edu.ng", User.Role.STAFF)
        self.admin = self.make("director@tsce.edu.ng", User.Role.ADMIN)

    def reset(self, user):
        return self.client.post(f"/api/staff/users/{user.pk}/reset-password", **self.csrf())

    def test_only_admins_can_reset(self):
        self.assertEqual(self.reset(self.student).status_code, 401)
        self.login("rabi@tsce.edu.ng")
        self.assertEqual(self.reset(self.student).status_code, 403)

    def test_admin_reset_issues_temporary_password_and_forces_change(self):
        self.login("director@tsce.edu.ng")
        res = self.reset(self.student)
        self.assertEqual(res.status_code, 200)
        temp = res.json()["temporaryPassword"]
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password(temp))
        self.assertTrue(self.student.must_change_password)
        self.assertFalse(self.student.check_password(PW))

    def test_admin_cannot_reset_another_admin_unless_superuser(self):
        other = self.make("bursar@tsce.edu.ng", User.Role.ADMIN)
        self.login("director@tsce.edu.ng")
        self.assertEqual(self.reset(other).status_code, 403)
        User.objects.filter(pk=self.admin.pk).update(is_superuser=True)
        self.assertEqual(self.reset(other).status_code, 200)
