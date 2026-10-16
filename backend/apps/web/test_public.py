"""The public website, rendered by Django at its usual addresses."""
from datetime import date, timedelta

from django.utils import timezone

from apps.academics.models import Certificate, Enrollment, Student
from apps.comms.models import Announcement, Enquiry, Notification
from apps.core.models import SiteSettings
from apps.programmes.models import Cohort, Programme

from .tests import WebTestCase


class PublicPagesTests(WebTestCase):
    def test_every_page_renders_at_its_usual_address(self):
        for url in ("/", "/index.html", "/pages/about.html", "/pages/programmes.html", "/pages/admissions.html",
                    "/pages/news.html", "/pages/contact.html", "/pages/verify.html"):
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, url)
            self.assertContains(res, "/js/site.js?v=")

    def test_dates_and_discounts_come_from_settings(self):
        Cohort.objects.update(start_date=date(2026, 10, 19), early_bird_deadline=date(2026, 10, 19), enrolment_closes=date(2026, 10, 19))
        SiteSettings.objects.update(early_bird_pct=20)
        home = self.client.get("/")
        self.assertContains(home, "Monday, 19 October 2026")            # announcement bar + cohort block
        self.assertContains(home, "20% Early-Bird")
        self.assertContains(home, 'data-start="2026-10-19"')
        self.assertNotContains(home, "Pay before 1 October")
        adm = self.client.get("/pages/admissions.html")
        self.assertContains(adm, "Early bird (−20%)")
        self.assertContains(adm, "₦40,000")  # ₦50,000 − 20% in the fee table

    def test_featured_cards_and_details(self):
        home = self.client.get("/")
        self.assertEqual(home.content.decode().count('class="prog-card reveal"'), 6)
        self.assertContains(home, 'id="p-fullstack"')
        Programme.objects.filter(slug="cad").update(status=Programme.Status.INACTIVE)
        page = self.client.get("/pages/programmes.html")
        self.assertNotContains(page, 'data-prog="cad"')
        self.assertContains(page, "10 programmes")

    def test_catalogue_filters_without_js(self):
        page = self.client.get("/pages/programmes.html?track=Security")
        self.assertEqual(page.content.decode().count('class="prog-card reveal"'), 2)
        page = self.client.get("/pages/programmes.html?q=excel")
        self.assertContains(page, "IT Essentials and Digital Literacy")
        self.assertContains(page, "1 programme<")
        self.assertContains(self.client.get("/pages/programmes.html?q=zzzz"), 'id="progEmpty">')
        self.assertContains(self.client.get("/pages/programmes.html?id=cad"), 'link-modal open" id="p-cad"')

    def test_installment_faq_follows_the_setting(self):
        self.assertContains(self.client.get("/pages/admissions.html"), "pay 50% of the programme fee")
        SiteSettings.objects.update(allow_installments=False)
        self.assertContains(self.client.get("/pages/admissions.html"), "fees are paid in full online")

    def test_no_discontinued_or_demo_content(self):
        for url in ("/", "/pages/programmes.html", "/pages/admissions.html", "/pages/news.html", "/pages/about.html"):
            body = self.client.get(url).content.decode()
            self.assertNotIn("40% scholarship", body, url)
            self.assertNotIn("Performance Scholarship", body, url)
            self.assertNotIn("Demo profiles", body, url)

    def test_news(self):
        Announcement.objects.create(title="Orientation", body="Saturday at the main hall.", audience="Public", status="Published",
                                    tag="Event", published_at=timezone.now())
        Announcement.objects.create(title="Staff memo", body="x", audience="Staff", status="Published")
        page = self.client.get("/pages/news.html")
        self.assertContains(page, "Orientation")
        self.assertContains(page, "main hall")
        self.assertNotContains(page, "Staff memo")

    def test_contact_form(self):
        res = self.client.post("/pages/contact.html", {"name": "Musa", "email": "bad", "phone": "1", "message": "short"})
        self.assertContains(res, "valid Nigerian phone number")
        self.assertEqual(Enquiry.objects.count(), 0)
        res = self.client.post("/pages/contact.html", {"name": "Musa Ali", "email": "musa@example.com", "phone": "08061234567",
                                                       "programme": "Network Engineering", "message": "Do you have weekend classes?"})
        self.assertContains(res, "Message sent")
        self.assertContains(res, "Thank you, Musa.")
        self.assertEqual(Enquiry.objects.get().phone, "0806 123 4567")

    def test_contact_staff_alert(self):
        from apps.accounts.models import User

        staff = User.objects.create_user("rabi@tsce.edu.ng", "x-Pass-2026!", full_name="Rabi", role="staff")
        self.client.post("/pages/contact.html", {"name": "Musa Ali", "email": "musa@example.com", "phone": "08061234567",
                                                 "message": "Do you have weekend classes?"})
        self.assertTrue(Notification.objects.filter(recipient=staff, title="New enquiry").exists())

    def test_certificate_check(self):
        user = self.account()
        app = self.make_app(user, status="Enrolled", payment_status="Paid")
        st = Student.objects.create(user=user, student_no="TSCE/2026/00001", first_name="Aisha", last_name="Garba", gender="Female", phone=app.phone)
        en = Enrollment.objects.create(student=st, application=app, programme=app.programme, cohort=app.cohort, schedule=app.schedule,
                                       start_date=date(2026, 10, 12), end_date=date(2026, 10, 12) + timedelta(days=60))
        cert = Certificate.objects.create(number="TSCE/CERT/2026/00001", enrollment=en, issued_at=timezone.now())
        self.assertContains(self.client.get("/pages/verify.html?no=tsce/cert/2026/00001"), "Certificate verified")
        self.assertContains(self.client.get("/pages/verify.html?no=TSCE/CERT/2026/99999"), "No certificate found")
        Certificate.objects.filter(pk=cert.pk).update(status=Certificate.Status.REVOKED)
        self.assertContains(self.client.get("/pages/verify.html?no=TSCE/CERT/2026/00001"), "revoked")
