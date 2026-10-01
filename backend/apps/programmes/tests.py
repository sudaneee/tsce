import json
from datetime import date
from io import StringIO

from django.core.management import call_command
from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.models import User
from apps.academics.grading import grade_for
from apps.academics.models import Enrollment, Student
from apps.admissions.models import Application
from apps.core.models import Sequence, SiteSettings
from apps.payments.models import Payment
from apps.programmes.management.commands.seed_school import CATALOGUE
from apps.programmes.models import Cohort, Module, Programme


def seed(*args):
    call_command("seed_school", *args, stdout=StringIO(), stderr=StringIO())


class SeedSchoolTests(TestCase):
    def test_seeds_flyer_data_and_nothing_personal(self):
        seed()
        flyer = json.loads(CATALOGUE.read_text(encoding="utf-8"))
        self.assertEqual(Programme.objects.count(), 11)
        self.assertEqual(Module.objects.count(), sum(len(p["modules"]) for p in flyer["programmes"]))

        fs = Programme.objects.get(slug="fullstack")
        self.assertEqual((fs.code, fs.fee, fs.weeks), ("TSCE-FSE", 50000, 10))
        self.assertEqual(fs.schedules[0], "Weekday Morning (9:00am – 12:00pm)")  # en dash survives
        self.assertIsNone(fs.instructor)  # demo instructor names are not seeded

        s = SiteSettings.load()
        self.assertEqual(s.institution_name, "Trust Skill Acquisition Centre of Excellence")
        self.assertEqual((s.early_bird_pct, s.excellence_pct, s.application_fee), (15, 50, 5000))
        self.assertEqual(s.current_cohort.start_date, date(2026, 10, 12))
        self.assertEqual(s.current_cohort.early_bird_deadline, date(2026, 10, 1))

        # Production starts empty of people and transactions
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Application.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)

    def test_rerun_keeps_staff_edits_unless_update(self):
        seed()
        Programme.objects.filter(slug="cad").update(fee=60000)
        SiteSettings.objects.filter(pk=1).update(accepting_applications=False)

        seed()
        self.assertEqual(Programme.objects.get(slug="cad").fee, 60000)
        self.assertFalse(SiteSettings.load().accepting_applications)
        self.assertEqual(Programme.objects.count(), 11)

        seed("--update")
        self.assertEqual(Programme.objects.get(slug="cad").fee, 50000)
        self.assertEqual(Module.objects.filter(programme__slug="cad").count(), 8)


class CoreModelTests(TestCase):
    def test_sequence_counts_up_per_name(self):
        self.assertEqual([Sequence.next("app") for _ in range(3)], [1, 2, 3])
        self.assertEqual(Sequence.next("tx"), 1)

    def test_site_settings_is_a_singleton(self):
        seed()
        extra = SiteSettings(institution_name="Other", address="x")
        extra.save()
        self.assertEqual(SiteSettings.objects.count(), 1)
        with self.assertRaises(RuntimeError):
            SiteSettings.load().delete()


class AcademicsModelTests(TestCase):
    def test_grade_bands(self):
        self.assertEqual([grade_for(s) for s in (100, 80, 79, 70, 60, 50, 49, 0)], list("AABBCDFF"))

    def test_module_progress_is_derived_from_overall_progress(self):
        seed()
        programme = Programme.objects.get(slug="cad")  # 8 modules
        enrollment = Enrollment(programme=programme, progress=78)
        pcts = [pct for _, pct in enrollment.module_progress()]
        self.assertEqual(pcts, [100, 100, 100, 100, 100, 100, 24, 0])
        enrollment.progress = 100
        self.assertTrue(all(pct == 100 for _, pct in enrollment.module_progress()))


class ConstraintTests(TestCase):
    def test_refund_requires_parent_charge(self):
        with self.assertRaises(IntegrityError):
            Payment.objects.create(reference="TSCE-ZP-X-RF", kind="refund", name="A", email="a@x.ng",
                                   description="Refund", amount=100, gateway="zainpay")

    def test_one_enrollment_per_programme_and_cohort(self):
        seed()
        user = User.objects.create_user("s@x.ng", "pw-123456!", full_name="S T")
        student = Student.objects.create(user=user, student_no="TSCE/2026/00001", first_name="S", last_name="T",
                                         gender="Female", phone="0803")
        programme, cohort = Programme.objects.get(slug="cad"), Cohort.objects.get()
        common = dict(programme=programme, cohort=cohort, fee=50000, amount_payable=50000, first_name="S",
                      last_name="T", gender="Female", dob=date(2000, 1, 1), phone="0803", email="s@x.ng",
                      address="Zaria", state="Kaduna", lga="Zaria", qualification="B.Sc", institution="ABU",
                      waec_status="Not Applicable", schedule="Weekend", user=user)
        a1 = Application.objects.create(number="TSCE/APP/2026/00001", **common)
        a2 = Application.objects.create(number="TSCE/APP/2026/00002", **common)
        dates = dict(start_date=cohort.start_date, end_date=programme.end_date_from(cohort.start_date))
        Enrollment.objects.create(student=student, application=a1, programme=programme, cohort=cohort, **dates)
        with self.assertRaises(IntegrityError):
            Enrollment.objects.create(student=student, application=a2, programme=programme, cohort=cohort, **dates)
