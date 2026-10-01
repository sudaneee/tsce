from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
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
        extra.setdefault("email_verified_at", timezone.now())
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


@override_settings(CACHES=LOCMEM, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RegistrationTests(AuthTestCase):
    def register(self, **over):
        data = {"accountType": "parent", "fullName": "Hajiya Rabi Musa", "email": "Rabi.Musa@example.com",
                "phone": "0803 123 4567", "password": PW, **over}
        with self.captureOnCommitCallbacks(execute=True):  # the email is sent after commit
            return self.client.post("/api/auth/register", data, format="json", **self.csrf())

    def link_token(self):
        from django.core import mail
        body = mail.outbox[-1].body
        return body.split("verify-email.html?token=")[1].split()[0]

    def test_register_sends_verification_and_blocks_login_until_verified(self):
        from django.core import mail
        res = self.register()
        self.assertEqual(res.status_code, 201)
        user = User.objects.get()
        self.assertEqual((user.email, user.role, user.phone, user.email_verified), ("rabi.musa@example.com", "parent", "0803 123 4567", False))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("verify-email.html?token=", mail.outbox[0].body)

        res = self.login("rabi.musa@example.com")
        self.assertEqual((res.status_code, res.json()["code"]), (400, "email_unverified"))
        self.assertEqual(len(mail.outbox), 2)  # a fresh link on each blocked login

        res = self.client.post("/api/auth/verify-email", {"token": self.link_token()}, format="json", **self.csrf())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["user"]["role"], "parent")
        self.assertTrue(self.client.get("/api/auth/me").json()["user"]["emailVerified"])  # signed in

    def test_old_link_does_not_sign_in_again(self):
        self.register(accountType="student")
        token = self.link_token()
        self.client.post("/api/auth/verify-email", {"token": token}, format="json", **self.csrf())
        self.client.post("/api/auth/logout", **self.csrf())
        res = self.client.post("/api/auth/verify-email", {"token": token}, format="json", **self.csrf())
        self.assertEqual(res.json(), {"user": None, "alreadyVerified": True})
        self.assertIsNone(self.client.get("/api/auth/me").json()["user"])
        self.assertEqual(User.objects.get().role, "applicant")

    def test_bad_or_tampered_token(self):
        res = self.client.post("/api/auth/verify-email", {"token": "nonsense"}, format="json", **self.csrf())
        self.assertEqual(res.json()["code"], "invalid_token")

    def test_existing_email_gets_same_answer_and_no_new_account(self):
        from django.core import mail
        self.make("taken@example.com", User.Role.APPLICANT, email_verified_at=timezone.now())
        res = self.register(email="taken@example.com")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(User.objects.count(), 1)
        self.assertIn("already exists", mail.outbox[-1].body)

    def test_validation(self):
        res = self.register(phone="123", password="password", accountType="teacher", email="nope")
        self.assertEqual(set(res.json()["fields"]), {"phone", "accountType", "email"})
        res = self.register(password="password")
        self.assertEqual(list(res.json()["fields"]), ["password"])

    def test_resend_is_silent_about_unknown_emails(self):
        from django.core import mail
        self.register()
        mail.outbox.clear()
        for email in ("rabi.musa@example.com", "nobody@example.com"):
            res = self.client.post("/api/auth/resend-verification", {"email": email}, format="json", **self.csrf())
            self.assertEqual(res.json(), {"ok": True})
        self.assertEqual(len(mail.outbox), 1)
