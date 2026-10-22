"""Browser test of the server-rendered staff portal: dashboard, applications, awards, payments, staff, settings."""
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


def login(page, email, pw, landing="**/staff/"):
    page.goto(f"{B}/account/login/?role=staff"); page.wait_for_selector("#loginForm")
    page.fill("#loginEmail", email); page.fill("#loginPassword", pw)
    page.click("#loginForm button[type=submit]"); page.wait_for_url(landing)


with sync_playwright() as p:
    browser = p.chromium.launch(channel=os.environ.get("E2E_BROWSER", "msedge"), headless=True)
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)

    # ---------- Admissions officer ----------
    login(page, "rabi@tsce.edu.ng", "Staff-Pass-2026")
    kpis = flat(page.inner_text(".kpis"))
    check("dashboard: real numbers (3 applications, 1 enrolled)", "Applications 3" in kpis and "Enrolled 1" in kpis, kpis[:300])
    check("sidebar: 1 award to verify", page.inner_text('[data-count-for="staff-scholarships"]') == "1")
    check("sidebar: 1 duplicate payment", page.inner_text('[data-count-for="staff-payments"]') == "1")
    check("sidebar: unwired pages marked soon", page.locator('.sb-link[aria-disabled="true"]').count() == 6)
    check("non-admin: no Staff / Settings", page.locator('.sb-link[href="/staff/team/"], .sb-link[href="/staff/settings/"]').count() == 0)
    res = page.goto(f"{B}/staff/settings/")
    check("non-admin: settings forbidden", res.status == 403)
    page.goto(f"{B}/pages/staff/dashboard.html"); page.wait_for_url("**/staff/")
    check("old dashboard address redirects", page.url.endswith("/staff/"))

    # Bell (server notifications)
    check("bell: unread from server", page.inner_text("#bellCount") == "1")
    page.click("#bellBtn"); page.click("#bellReadAll"); page.wait_for_load_state("load")
    check("bell: mark all read", page.locator("#bellCount").count() == 0)

    # Applications list + actions
    page.goto(f"{B}/staff/applications/"); page.wait_for_selector("#appTable tbody tr")
    check("applications: 3 rows", page.locator("#appTable tbody tr").count() == 3)
    check("applications: status chips", "Awaiting Verification 1" in flat(page.inner_text("#statusChips")))
    page.fill("#aSearch", "aisha"); page.press("#aSearch", "Enter"); page.wait_for_load_state("load")
    check("applications: search", page.locator("#appTable tbody tr").count() == 1)
    page.click("#appTable tbody tr a.ref"); page.wait_for_selector("#appDetail")
    detail = page.inner_text("#appDetail")
    check("detail: application fee included in the programme fee", "included in the programme fee" in detail and "55,000" in detail)
    page.click('[data-act="remind"]'); page.wait_for_selector(".toast-msg")
    check("remind: sent", "reminded about the programme fee" in page.inner_text(".toast-msg"))
    page.fill("#id_note", "Incomplete details"); page.click('[data-act="reject"]'); page.wait_for_selector(".toast-msg")
    check("reject: status updated", "Rejected" in page.inner_text(".view-head"))

    # Excellence Awards: verify Umar
    page.goto(f"{B}/staff/awards/"); page.wait_for_selector("#awTable tbody tr")
    check("awards: Umar waiting", "Umar Bello" in page.inner_text("#awTable") and "Awaiting Verification" in page.inner_text("#awTable"))
    page.click("#awTable >> text=Verify"); page.wait_for_selector('button[value="award-yes"]')
    check("detail: verification instructions", "original" in page.inner_text("#appDetail"))
    page.fill("#id_note", "Original WAEC seen"); page.click('button[value="award-yes"]'); page.wait_for_selector(".toast-msg")
    check("award approved → admitted at 50%", "approved" in page.inner_text(".toast-msg") and "Admitted" in page.inner_text(".view-head"))
    page.goto(f"{B}/staff/awards/?tab=Approved")
    check("awards: now approved", "Umar Bello" in page.inner_text("#awTable"))

    # Payments: duplicate refund
    page.goto(f"{B}/staff/payments/"); page.wait_for_selector("#payTable tbody tr")
    check("payments: duplicate flagged", page.locator("#payTable .badge:has-text('Duplicate')").count() == 1)
    page.check("#tDup"); page.click(".table-tools button[type=submit]"); page.wait_for_load_state("load")
    page.click("#payTable tbody tr a.ref"); page.wait_for_selector("#rfForm")
    page.fill("#id_transferRef", "JAIZ-778899"); page.click("#rfSave"); page.wait_for_selector(".toast-msg")
    check("refund recorded", "Refund of" in page.inner_text(".toast-msg"))
    page.goto(f"{B}/staff/payments/")
    check("payments: refund row recorded", "TSCE-ZP-20261001-000012-RF" in page.inner_text("#payTable"))
    check("payments: duplicates KPI back to 0", "Duplicates to refund 0" in flat(page.inner_text("#payKpis")))
    with page.expect_download() as dl:
        page.click("#expPay")
    check("payments: CSV export", dl.value.suggested_filename == "tsce-payments.csv")

    # Search
    page.fill("#gSearch", "zainab"); page.press("#gSearch", "Enter"); page.wait_for_selector("#searchResults")
    found = page.inner_text("#searchResults")
    check("search finds application + student + payments", "TSCE/APP/2026/00003" in found and "TSCE/2026/00001" in found)
    ctx.close()

    # ---------- Admin ----------
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)
    login(page, "director@tsce.edu.ng", "Director-Pass-2026")
    page.goto(f"{B}/staff/team/"); page.wait_for_selector("#sfT tbody tr")
    check("staff list shows existing accounts", "Test Director" in page.inner_text("#sfT") and "Rabi Isa" in page.inner_text("#sfT"))
    page.click("#addStaff"); page.fill("#st_n", "Kamal Shehu"); page.fill("#st_t", "Bursar"); page.fill("#st_e", "bursary@tsce.edu.ng")
    page.fill("#st_p", "0803 111 2222"); page.select_option("#st_d", "Finance"); page.click("#stSave")
    page.wait_for_selector("#tempPassword")
    temp = page.inner_text("#tempPassword").strip()
    check("new staff gets a temporary password", len(temp) == 10)
    page.goto(f"{B}/staff/team/new/"); page.fill("#st_n", "Engr. Musa Garba"); page.fill("#st_t", "Instructor — Networking")
    page.select_option("#st_d", "Academics"); page.select_option("#st_a", "none"); page.click("#stSave")
    page.wait_for_url("**/staff/team/")
    check("instructor added without login", "No login" in page.locator("#sfT tr", has_text="Musa Garba").inner_text())

    page.goto(f"{B}/staff/settings/"); page.wait_for_selector("#admissions")
    check("settings: payments read-only info", "₦300" in page.inner_text("#pay") and "Bank transfer" in page.inner_text("#pay"))
    page.fill("#id_admissions-opens", "2026-09-01"); page.fill("#id_admissions-applicationFee", "6000")
    page.click("#admissions button.btn-primary"); page.wait_for_selector(".toast-msg")
    page.goto(f"{B}/staff/settings/")
    check("settings: application fee + opening date saved",
          page.input_value("#id_admissions-applicationFee") == "6000" and page.input_value("#id_admissions-opens") == "2026-09-01")
    page.goto(f"{B}/pages/admissions.html")
    check("settings: new application fee shown on the public site", "₦6,000 application fee" in page.inner_text("main"))
    ctx.close()

    # The new bursar signs in with the temporary password and must change it
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)
    login(page, "bursary@tsce.edu.ng", temp, landing="**/account/password/?next=*")
    check("new staff forced to choose a password", page.locator("#id_new_password1").count() == 1)
    page.fill("#id_old_password", temp); page.fill("#id_new_password1", "Bursar-Pass-2027"); page.fill("#id_new_password2", "Bursar-Pass-2027")
    page.click("main button[type=submit]"); page.wait_for_url("**/staff/")
    check("after choosing a password the bursar reaches the dashboard", page.url.endswith("/staff/"))
    browser.close()

for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or not detail else f" — {detail[:300]}"))
print("JS errors:", errors or "none")
sys.exit(0 if all(ok for _, ok, _ in results) and not errors else 1)
