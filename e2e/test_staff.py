"""Browser test of the staff portal (Phase 5): dashboard, applications, awards, payments, staff, settings."""
import os
import sys

from playwright.sync_api import sync_playwright

B = os.environ.get("E2E_BASE", "http://localhost:8765")
results, errors = [], []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


def watch(page):
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e} @ {page.url}"))
    page.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and errors.append(f"console: {m.text} @ {page.url}"))


def flat(text):
    return " ".join(text.split())


def login(page, email, pw):
    page.goto(f"{B}/pages/login.html?role=staff"); page.wait_for_selector("#loginForm")
    page.fill("#loginEmail", email); page.fill("#loginPassword", pw)
    page.click("#loginForm button[type=submit]"); page.wait_for_url("**/staff/dashboard.html")


with sync_playwright() as p:
    browser = p.chromium.launch(channel=os.environ.get("E2E_BROWSER", "msedge"), headless=True)
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)

    # ---------- Admissions officer ----------
    login(page, "rabi@tsce.edu.ng", "Staff-Pass-2026")
    page.wait_for_selector(".kpis .kpi")
    kpis = flat(page.inner_text(".kpis"))
    check("dashboard: real numbers (3 applications, 1 enrolled)", "Applications 3" in kpis and "Enrolled 1" in kpis, kpis[:300])
    check("dashboard: no demo figures", "324" not in page.inner_text("#view") and "11,850,000" not in page.inner_text("#view"))
    page.wait_for_selector('[data-count-for="staff-scholarships"]:not([hidden])')
    check("sidebar: 1 award to verify", page.inner_text('[data-count-for="staff-scholarships"]') == "1")
    check("sidebar: 1 duplicate payment", page.inner_text('[data-count-for="staff-payments"]') == "1")
    check("sidebar: unwired pages marked soon", page.locator('.sb-link[aria-disabled="true"]').count() == 7)
    check("non-admin: no Staff / Settings", page.locator('.sb-link[href="staff.html"], .sb-link[href="settings.html"]').count() == 0)
    page.goto(f"{B}/pages/staff/students.html"); page.wait_for_selector("#view .empty")
    check("unwired page shows Coming soon, not demo data", "Coming soon" in page.inner_text("#view"))

    # Bell (server notifications)
    page.wait_for_selector("#bellCount:not([hidden])")
    check("bell: unread from server", page.inner_text("#bellCount") == "1")
    page.click("#bellBtn"); page.click("#bellReadAll"); page.wait_for_selector("#bellCount[hidden]", state="attached")
    check("bell: mark all read", True)

    # Applications list + drawer actions
    page.goto(f"{B}/pages/staff/applications.html"); page.wait_for_selector("#appTable tbody tr")
    check("applications: 3 rows", page.locator("#appTable tbody tr").count() == 3)
    check("applications: status chips", "Awaiting Verification 1" in page.inner_text("#statusChips").replace("\n", " "))
    page.fill("#aSearch", "aisha"); page.wait_for_timeout(600)
    check("applications: search", page.locator("#appTable tbody tr").count() == 1)
    page.click("#appTable tbody tr"); page.wait_for_selector(".drawer.open .dr-body")
    check("drawer: shows unpaid application fee", "unpaid" in page.inner_text(".drawer.open .dr-body"))
    page.click('.drawer.open [data-act="remind"]'); page.wait_for_selector(".toast >> text=Reminder sent")
    check("remind: sent", True)
    page.click('.drawer.open [data-act="reject"]'); page.fill("#anNote", "Incomplete details"); page.click("#anOk")
    page.wait_for_selector(".toast >> text=Application rejected")
    page.wait_for_timeout(500)
    check("reject: status updated in list", "Rejected" in page.inner_text("#appTable"))

    # Excellence Awards: verify Umar
    page.goto(f"{B}/pages/staff/scholarships.html"); page.wait_for_selector("#awTable tbody tr")
    check("awards: Umar waiting", "Umar Bello" in page.inner_text("#awTable") and "Awaiting Verification" in page.inner_text("#awTable"))
    page.click("#awTable tbody tr"); page.wait_for_selector('.drawer.open [data-act="award-yes"]')
    check("drawer: verification instructions", "original" in page.inner_text(".drawer.open .dr-body"))
    page.click('.drawer.open [data-act="award-yes"]'); page.fill("#anNote", "Original WAEC seen"); page.click("#anOk")
    page.wait_for_selector(".toast >> text=Award approved")
    page.wait_for_timeout(500)
    page.click('#awTabs [data-tab="Approved"]')
    check("awards: now approved", "Umar Bello" in page.inner_text("#awTable"))

    # Payments: duplicate refund
    page.goto(f"{B}/pages/staff/payments.html"); page.wait_for_selector("#payTable tbody tr")
    check("payments: duplicate flagged", page.locator("#payTable .badge:has-text('Duplicate')").count() == 1)
    page.check("#tDup"); page.wait_for_timeout(600)
    page.click("#payTable tbody tr"); page.wait_for_selector(".drawer.open #pRefund")
    page.click("#pRefund"); page.fill("#rfRef", "JAIZ-778899"); page.click("#rfSave")
    page.wait_for_selector(".toast >> text=Refund recorded")
    page.uncheck("#tDup"); page.wait_for_timeout(700)
    check("payments: refund row recorded", "TSCE-ZP-20261001-000012-RF" in page.inner_text("#payTable"))
    check("payments: duplicates KPI back to 0", "Duplicates to refund 0" in flat(page.inner_text("#payKpis")))

    # Global search
    page.keyboard.press("Control+k"); page.fill("#gSearch", "zainab"); page.wait_for_selector("#gResults.open .sr-item")
    check("Ctrl K search finds application + student + payments", "TSCE/APP/2026/00003" in page.inner_text("#gResults") and "TSCE/2026/00001" in page.inner_text("#gResults"))
    ctx.close()

    # ---------- Admin ----------
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)
    login(page, "director@tsce.edu.ng", "Director-Pass-2026")
    page.goto(f"{B}/pages/staff/staff.html"); page.wait_for_selector("#sfT tbody tr")
    check("staff list shows existing accounts", "Test Director" in page.inner_text("#sfT") and "Rabi Isa" in page.inner_text("#sfT"))
    page.click("#addStaff"); page.fill("#st_n", "Kamal Shehu"); page.fill("#st_t", "Bursar"); page.fill("#st_e", "bursary@tsce.edu.ng")
    page.fill("#st_p", "0803 111 2222"); page.select_option("#st_d", "Finance"); page.click("#stSave")
    page.wait_for_selector(".modal >> text=Temporary password")
    temp = page.inner_text(".modal .mono").strip()
    check("new staff gets a temporary password", len(temp) == 10)
    page.click(".modal [data-close]")
    page.click("#addStaff"); page.fill("#st_n", "Engr. Musa Garba"); page.fill("#st_t", "Instructor — Networking")
    page.select_option("#st_d", "Academics"); page.select_option("#st_a", "none"); page.click("#stSave")
    page.wait_for_selector(".toast >> text=Staff added"); page.wait_for_timeout(500)
    check("instructor added without login", "No login" in page.locator("#sfT tr", has_text="Musa Garba").inner_text())

    page.goto(f"{B}/pages/staff/settings.html"); page.wait_for_selector("#adm")
    check("settings: payments read-only info", "₦300" in page.inner_text("#pay") and "Bank transfer" in page.inner_text("#pay"))
    page.fill("#a_o", "2026-09-01"); page.fill("#a_f", "6000"); page.click("#adm button.btn-primary")
    page.wait_for_selector(".toast >> text=Settings saved")
    site = page.evaluate("API.get('site').then(r => r.settings.admissions)")
    check("settings: application fee + opening date saved", site["applicationFee"] == 6000 and site["opens"] == "2026-09-01")
    ctx.close()

    # The new bursar signs in with the temporary password and must change it
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)
    login(page, "bursary@tsce.edu.ng", temp); page.wait_for_selector("#fpcForm")
    check("new staff forced to choose a password", page.is_visible("#fpcForm"))
    browser.close()

for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or not detail else f" — {detail[:300]}"))
print("JS errors:", errors or "none")
sys.exit(0 if all(ok for _, ok, _ in results) and not errors else 1)
