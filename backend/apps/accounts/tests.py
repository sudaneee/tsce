"""Accounts: sign-in rules, registration and verification, password resets (through the pages)."""
from io import StringIO

from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from . import services
from .models import StaffProfile, User

PW = "Zaria-Campus-2026"
LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(CACHES=LOCMEM, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AuthTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_school", stdout=StringIO())  # the pages show the school's details

    def setUp(self):
        cache.clear()  # rate-limit counters
        self.client = Client()

    def login(self, email, password=PW, **extra):
        return self.client.post("/account/login/", {"email": email, "password": password, **extra})

    def make(self, email, role, **extra):
        extra.setdefault("email_verified_at", timezone.now())
        return User.objects.create_user(email, PW, full_name=email.split("@")[0].title(), role=role, **extra)


class LoginTests(AuthTestCase):
    def test_email_is_case_insensitive(self):
        self.make("rabi@tsce.edu.ng", User.Role.STAFF)
        self.assertEqual(self.login("RABI@tsce.edu.ng")["Location"], "/staff/")

    def test_wrong_password_and_unknown_email_get_the_same_answer(self):
        self.make("amina@example.com", User.Role.STUDENT)
        wrong_pw, unknown = self.login("amina@example.com", "nope-nope-1"), self.login("ghost@example.com")
        self.assertContains(wrong_pw, "Incorrect email or password")
        self.assertContains(unknown, "Incorrect email or password")

    def test_disabled_account_is_explained_only_with_the_right_password(self):
        self.make("old@example.com", User.Role.STUDENT, is_active=False)
        self.assertContains(self.login("old@example.com"), "This account has been disabled")
        self.assertContains(self.login("old@example.com", "wrong-pw-123"), "Incorrect email or password")

    def test_login_requires_csrf_token(self):
        self.make("amina@example.com", User.Role.STUDENT)
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post("/account/login/", {"email": "amina@example.com", "password": PW}).status_code, 403)

    def test_remember_me_off_ends_session_with_browser(self):
        self.make("amina@example.com", User.Role.STUDENT)
        self.login("amina@example.com")  # "remember" unticked
        self.assertTrue(self.client.session.get_expire_at_browser_close())
        self.client.logout()
        self.login("amina@example.com", remember="on")
        self.assertFalse(self.client.session.get_expire_at_browser_close())


class PasswordTests(AuthTestCase):
    def test_change_password_keeps_session_and_clears_forced_change(self):
        user = self.make("amina@example.com", User.Role.STUDENT, must_change_password=True)
        self.client.force_login(user)
        bad = self.client.post("/account/password/", {"old_password": "wrong", "new_password1": "x", "new_password2": "y"})
        self.assertContains(bad, "Your old password was entered incorrectly")
        self.client.post("/account/password/", {"old_password": PW, "new_password1": "Kaduna-Road-2027",
                                                "new_password2": "Kaduna-Road-2027"})
        user.refresh_from_db()
        self.assertFalse(user.must_change_password)
        self.assertTrue(user.check_password("Kaduna-Road-2027"))
        self.assertEqual(self.client.get("/student/").status_code, 302)  # still signed in (no student record yet)

    def test_only_a_superuser_resets_another_admin(self):
        admin = self.make("director@tsce.edu.ng", User.Role.ADMIN)
        other = self.make("bursar@tsce.edu.ng", User.Role.ADMIN)
        profile = StaffProfile.objects.create(user=other, staff_no="STF-009", full_name="Bursar", title="Bursar",
                                              department="Finance")
        self.client.force_login(admin)
        self.assertEqual(self.client.post(f"/staff/team/{profile.pk}/", {"action": "reset"}).status_code, 403)
        User.objects.filter(pk=admin.pk).update(is_superuser=True)
        self.assertContains(self.client.post(f"/staff/team/{profile.pk}/", {"action": "reset"}), "Temporary password")
        other.refresh_from_db()
        self.assertTrue(other.must_change_password)

    def test_temporary_passwords_avoid_look_alike_characters(self):
        for _ in range(50):
            pw = services.temporary_password()
            self.assertEqual(len(pw), 10)
            self.assertFalse(set(pw) & set("0O1lI"))


class RegistrationTests(AuthTestCase):
    FORM = {"accountType": "parent", "fullName": "Hajiya Rabi Musa", "email": "rabi.musa@example.com",
            "phone": "0803 555 1234", "password": "Parent-Pass-2026", "password2": "Parent-Pass-2026"}

    def register(self, **over):
        return self.client.post("/account/register/", {**self.FORM, **over})

    def test_unverified_accounts_cant_sign_in(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.register()
        user = User.objects.get(email="rabi.musa@example.com")
        self.assertEqual((user.role, user.email_verified_at), ("parent", None))
        self.assertContains(self.login("rabi.musa@example.com", "Parent-Pass-2026"), "Please verify your email address first")

    def test_verification_token_rules(self):
        user = self.make("amina@example.com", User.Role.APPLICANT, email_verified_at=None)
        token = services.verification_token(user)
        _, newly = services.verify_email(token)
        self.assertTrue(newly)
        _, again = services.verify_email(token)
        self.assertFalse(again)  # an old link never signs anyone in again
        with self.assertRaises(services.InvalidToken):
            services.verify_email(token[:-2] + "xx")
        user.email = "changed@example.com"
        user.save()
        with self.assertRaises(services.InvalidToken):
            services.verify_email(token)  # bound to the email address it was sent to

    def test_existing_email_gets_same_answer_and_no_new_account(self):
        self.make("taken@example.com", User.Role.APPLICANT)
        self.assertContains(self.register(email="taken@example.com"), "Check your email")
        self.assertEqual(User.objects.count(), 1)
        self.assertIn("already exists", mail.outbox[-1].body)

    def test_validation(self):
        res = self.register(phone="123", accountType="teacher", email="nope")
        for message in ("valid Nigerian phone number", "Select a valid choice", "Enter a valid email address"):
            self.assertContains(res, message)
        self.assertContains(self.register(password="password", password2="password"), "This password is too common")

    def test_resend_is_silent_about_unknown_emails(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.register()
        mail.outbox.clear()
        for email in ("rabi.musa@example.com", "nobody@example.com"):
            self.assertContains(self.client.post("/account/resend-verification/", {"email": email}), "Check your email")
        self.assertEqual(len(mail.outbox), 1)
