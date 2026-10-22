"""The student portal: who may see what, withheld results, certificate rules, support."""
from datetime import date, timedelta

from django.utils import timezone

from apps.academics.models import AttendanceRecord, AttendanceSession, Certificate, Enrollment, Result, Student
from apps.accounts.models import User
from apps.comms.models import Announcement, Notification, SupportTicket

from .tests import PW, WebTestCase


class StudentPortalTestCase(WebTestCase):
    def enrol(self, account, first="Aisha", number="TSCE/APP/2026/00001", parent=False, **app_extra):
        app = self.make_app(account, number=number, first_name=first, status="Enrolled",
                            **{"payment_status": "Paid", "amount_paid": 55000, **app_extra})
        owner = {"guardian": account} if parent else {"user": account}
        student = Student.objects.create(**owner, student_no=f"TSCE/2026/{number[-5:]}", first_name=first, last_name="Garba",
                                         gender="Female", phone="0803 123 4567")
        enrollment = Enrollment.objects.create(student=student, application=app, programme=app.programme, cohort=app.cohort,
                                               schedule=app.schedule, start_date=date(2026, 10, 12),
                                               end_date=date(2026, 10, 12) + timedelta(days=67), amount_paid=app.amount_paid)
        return student, enrollment

    def setUp(self):
        super().setUp()
        self.user = self.account(role="student")
        self.student, self.enrollment = self.enrol(self.user)
        self.client.force_login(self.user)
        self.base = f"/student/{self.student.pk}/"


class AccessTests(StudentPortalTestCase):
    def test_student_lands_on_their_portal(self):
        self.client.logout()
        res = self.client.post("/account/login/", {"email": "aisha@example.com", "password": PW})
        self.assertEqual(res["Location"], "/student/")
        self.assertEqual(self.client.get("/student/")["Location"], self.base)
        for page in ("", "programme/", "attendance/", "results/", "certificate/", "payments/", "announcements/", "support/", "profile/"):
            self.assertEqual(self.client.get(self.base + page).status_code, 200, page)
        self.assertEqual(self.client.get("/pages/student/dashboard.html")["Location"], "/student/")

    def test_other_people_cant_open_it(self):
        self.client.force_login(self.account("x@example.com", name="X"))
        self.assertEqual(self.client.get(self.base).status_code, 404)
        self.client.force_login(User.objects.create_user("rabi@tsce.edu.ng", PW, full_name="Rabi", role="staff"))
        self.assertEqual(self.client.get(self.base)["Location"], "/staff/")
        self.client.logout()
        self.assertTrue(self.client.get(self.base)["Location"].startswith("/account/login/"))

    def test_parent_sees_each_child(self):
        parent = self.account("rabi@example.com", role="parent", name="Rabi Musa")
        a, _ = self.enrol(parent, first="Amina", number="TSCE/APP/2026/00002", parent=True)
        b, _ = self.enrol(parent, first="Umar", number="TSCE/APP/2026/00003", parent=True)
        self.client.force_login(parent)
        chooser = self.client.get("/student/")
        self.assertContains(chooser, "Amina Garba")
        self.assertContains(chooser, "Umar Garba")
        page = self.client.get(f"/student/{a.pk}/")
        self.assertContains(page, "Welcome, Amina")
        self.assertContains(page, f"/student/{b.pk}/")  # sibling switcher
        self.assertEqual(self.client.get(self.base).status_code, 404)  # not their child
        self.assertContains(self.client.get("/my-applications/"), f"/student/{a.pk}/")


class AcademicsTests(StudentPortalTestCase):
    def test_results_withheld_until_fees_are_cleared(self):
        Result.objects.create(enrollment=self.enrollment, module=self.enrollment.programme.modules.first(), type="Module Test",
                              score=82, status="Published", assessed_on=date(2026, 10, 20))
        Result.objects.create(enrollment=self.enrollment, module=self.enrollment.programme.modules.last(), type="Project",
                              score=40, status="Draft", assessed_on=date(2026, 10, 21))
        page = self.client.get(self.base + "results/")
        self.assertContains(page, "82%")
        self.assertNotContains(page, "40%")  # drafts are hidden
        self.enrollment.application.__class__.objects.filter(pk=self.enrollment.application_id).update(
            payment_status="Part Paid", amount_paid=30000, balance_due_date=date(2026, 12, 18))
        page = self.client.get(self.base + "results/")
        self.assertContains(page, "Results are withheld")
        self.assertNotContains(page, "82%")
        self.assertContains(page, "Pay balance · ₦25,300")
        self.assertContains(self.client.get(self.base), "Programme fee balance: ₦25,000")

    def test_attendance_rate(self):
        e = self.enrollment
        for i, status in enumerate(["Present", "Late", "Absent", "Present"]):
            s = AttendanceSession.objects.create(programme=e.programme, cohort=e.cohort, date=date(2026, 10, 12) + timedelta(days=i))
            AttendanceRecord.objects.create(session=s, enrollment=e, status=status)
        page = self.client.get(self.base + "attendance/")
        self.assertContains(page, "75%")       # present + late = 3 of 4
        self.assertContains(page, "On track")

    def test_certificate_requirements_and_issued(self):
        page = self.client.get(self.base + "certificate/")
        self.assertContains(page, "In Progress")
        self.assertContains(page, "Attendance of at least 75%")
        Certificate.objects.create(number="TSCE/CERT/2026/00001", enrollment=self.enrollment, issued_at=timezone.now())
        page = self.client.get(self.base + "certificate/")
        self.assertContains(page, "Certificate issued")
        self.assertContains(page, "/pages/verify.html?no=TSCE/CERT/2026/00001")

    def test_programme_and_announcements(self):
        self.assertContains(self.client.get(self.base + "programme/"), self.enrollment.programme.modules.first().title)
        Announcement.objects.create(title="Lab closed Friday", body="x", audience="Students", status="Published")
        Announcement.objects.create(title="Staff only", body="x", audience="Staff", status="Published")
        page = self.client.get(self.base + "announcements/")
        self.assertContains(page, "Lab closed Friday")
        self.assertNotContains(page, "Staff only")


class SupportAndProfileTests(StudentPortalTestCase):
    def test_ticket_reply_round_trip(self):
        staff = User.objects.create_user("rabi@tsce.edu.ng", PW, full_name="Rabi", role="staff")
        res = self.client.post(self.base + "support/", {"category": "Payments", "subject": "Receipt name", "message": "Please fix the name."})
        self.assertEqual(res["Location"], self.base + "support/")
        t = SupportTicket.objects.get()
        self.assertTrue(t.number.startswith("TKT-"))
        self.assertTrue(Notification.objects.filter(recipient=staff, title="New support ticket").exists())
        self.client.force_login(staff)
        self.assertContains(self.client.get("/staff/support/"), "Receipt name")
        self.client.post(f"/staff/support/{t.pk}/", {"reply": "Fixed — download it again.", "resolve": "1"})
        t.refresh_from_db()
        self.assertEqual((t.status, t.replied_by), ("Resolved", staff))
        self.assertTrue(Notification.objects.filter(recipient=self.user, title__startswith="Reply to your ticket").exists())
        self.client.force_login(self.user)
        self.assertContains(self.client.get(self.base + "support/"), "Fixed — download it again.")

    def test_profile_edit(self):
        res = self.client.post(self.base + "profile/", {"phone": "+234 806 111 2222", "address": "Samaru", "emergency_contact": "Mum 0803"})
        self.assertEqual(res["Location"], self.base + "profile/")
        self.student.refresh_from_db()
        self.assertEqual((self.student.phone, self.student.emergency_contact), ("0806 111 2222", "Mum 0803"))
        self.assertContains(self.client.post(self.base + "profile/", {"phone": "123"}), "valid Nigerian phone number")
