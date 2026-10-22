"""Admissions rules, tested directly on the service and the discount rules (the pages are tested in apps/web)."""
from datetime import date
from io import StringIO
from unittest import mock

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.comms.models import Notification
from apps.core.exceptions import ServiceError
from apps.core.models import SiteSettings
from apps.programmes.models import Cohort, Programme

from .discounts import admissions_state, early_bird_open
from .models import Application, AwardRequest
from .services import create_application

OCT_1, SEP_30 = date(2026, 10, 1), date(2026, 9, 30)
PW = "x-Pass-2026!"


def on(day):
    """Freeze 'today' (Lagos) for the admissions rules."""
    return mock.patch("django.utils.timezone.localdate", return_value=day)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AdmissionsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_school", stdout=StringIO())

    def setUp(self):
        cache.clear()

    def account(self, email="aisha@example.com", role=User.Role.APPLICANT, verified=True, name="Aisha Garba"):
        return User.objects.create_user(email, PW, full_name=name, role=role, phone="0803 123 4567",
                                        email_verified_at=timezone.now() if verified else None)

    def data(self, **over):
        """What the application form hands the service after validation."""
        prog = Programme.objects.get(slug=over.pop("programme", "fullstack"))
        d = {"firstName": "Aisha", "middleName": "", "lastName": "Garba", "gender": "Female", "dob": date(2002, 5, 14),
             "phone": "0803 123 4567", "email": "", "address": "12 Samaru Road, Zaria", "state": "Kaduna", "lga": "Zaria",
             "qualification": "OND", "institution": "Nuhu Bamalli Polytechnic", "gradYear": 2023,
             "waecStatus": "Available", "waecYear": 2022, "numAs": 6, "resultFile": None,
             "programmeId": prog, "schedule": prog.schedules[0], "awardRequest": "none", "declare": True}
        d.update(over)
        return d

    def apply(self, user, day=OCT_1, **over):
        with on(day):
            return create_application(self.data(**over), user)

    def refused(self, user, code, **over):
        with self.assertRaises(ServiceError) as ctx:
            self.apply(user, **over)
        self.assertEqual(ctx.exception.code, code)
        return ctx.exception


class CalendarTests(AdmissionsTestCase):
    def test_early_bird_ends_on_the_deadline_day(self):
        cohort = Cohort.objects.get()
        Cohort.objects.update(early_bird_deadline=OCT_1)
        cohort.refresh_from_db()
        self.assertTrue(early_bird_open(cohort, SEP_30))
        self.assertFalse(early_bird_open(cohort, OCT_1))

    def test_application_window(self):
        s = SiteSettings.load()
        self.assertTrue(admissions_state(s, OCT_1).open)
        self.assertIn("closed on 12 October 2026", admissions_state(s, date(2026, 10, 13)).message)


class CreateApplicationTests(AdmissionsTestCase):
    def test_only_verified_applicant_accounts(self):
        self.refused(self.account(verified=False), "email_unverified")
        self.refused(self.account("rabi@tsce.edu.ng", role=User.Role.STAFF, name="Rabi"), "staff_account")
        self.assertEqual(Application.objects.count(), 0)

    def test_self_applicant_is_admitted_with_the_application_fee_added(self):
        user = self.account()
        app = self.apply(user, email="someone.else@example.com")
        self.assertEqual((app.number, app.status, app.application_fee), ("TSCE/APP/2026/00001", "Admitted", 5000))
        self.assertEqual((app.fee, app.amount_payable), (50000, 55000))
        self.assertEqual(app.email, "aisha@example.com")  # self-applicants always use their account email
        self.assertTrue(Notification.objects.filter(recipient=user, title="Admission approved").exists())

    def test_parent_applies_for_several_children_and_duplicates_are_refused(self):
        parent = self.account("rabi.musa@example.com", role=User.Role.PARENT, name="Rabi Musa")
        a = self.apply(parent, firstName="Aisha", lastName="Musa", email="aisha.musa@example.com")
        b = self.apply(parent, firstName="Umar", lastName="Musa", gender="Male", dob=date(2005, 1, 2), programme="network")
        self.assertEqual((a.email, b.email), ("aisha.musa@example.com", ""))
        self.assertEqual(set(parent.applications.values_list("first_name", flat=True)), {"Aisha", "Umar"})
        exc = self.refused(parent, "duplicate_application", firstName="aisha", lastName="MUSA")
        self.assertEqual(exc.extra["applicationId"], a.number)

    def test_closed_admissions_and_full_programmes(self):
        user = self.account()
        SiteSettings.objects.filter(pk=1).update(accepting_applications=False)
        self.refused(user, "admissions_closed")
        SiteSettings.objects.filter(pk=1).update(accepting_applications=True)
        self.assertIn("closed on 12 October 2026", self.refused(user, "admissions_closed", day=date(2026, 10, 13)).message)
        Programme.objects.filter(slug="fullstack").update(capacity=0)
        self.assertEqual(self.refused(user, "programme_full").field, "programmeId")

    def test_excellence_award_request(self):
        user = self.account()
        self.refused(user, "not_eligible", awardRequest="excellence", waecYear=2018)
        app = self.apply(user, awardRequest="excellence")
        self.assertEqual(app.status, "Awaiting Verification")
        award = AwardRequest.objects.get()
        self.assertEqual((award.type, award.requested_pct, award.status), ("excellence", 50, "Pending"))
