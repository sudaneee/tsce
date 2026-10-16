"""
Browser test of the full admissions journey on the server-rendered pages:

parent registers → verifies email (link read from the dev server's console email)
→ applies for two children (nothing to pay to apply)
→ child 1 admitted immediately → pays programme fee incl. ₦5,000 application fee → enrolled
→ child 2 requested the Excellence Award → awaiting verification → staff approve
→ parent pays 50% of tuition + the application fee → enrolled
"""
import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

B = os.environ.get("E2E_BASE", "http://localhost:8765")
LOG = os.environ["E2E_SERVER_LOG"]
results, errors = [], []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


def watch(page):
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e} @ {page.url}"))
    page.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and errors.append(f"console: {m.text} @ {page.url}"))


def latest_verification_link(email):
    """The dev server prints emails to its console; find the newest link sent to `email`."""
    for _ in range(20):
        text = open(LOG, encoding="utf-8", errors="replace").read()
        blocks = [b for b in text.split("To: ") if b.startswith(email)]
        links = re.findall(r"(http\S+/account/verify-email/\?token=\S+)", blocks[-1]) if blocks else []
        if links:
            return links[-1]
        time.sleep(0.5)
    return None


def apply_for_child(page, first, dob, programme, award=False):
    page.goto(f"{B}/apply/?new=1&programme={programme}"); page.wait_for_selector("#a_first")
    page.fill("#a_first", first); page.fill("#a_last", "Musa")
    page.select_option("#a_gender", "Female" if first == "Aisha" else "Male"); page.fill("#a_dob", dob)
    page.select_option("#a_state", "Kaduna"); page.fill("#a_address", "5 Kongo Road, Zaria"); page.fill("#a_lga", "Zaria")
    page.click("#nextBtn"); page.wait_for_selector("#a_qual")
    page.select_option("#a_qual", "SSCE"); page.fill("#a_grad", "2024"); page.fill("#a_inst", "Barewa College")
    page.select_option("#a_waec", "Available"); page.fill("#a_waecYear", "2024"); page.fill("#a_numAs", "7" if award else "3")
    page.click("#nextBtn"); page.wait_for_selector("#a_schedule")
    check(f"{first}: programme pre-selected", page.is_checked(f'#progPicker input[value="{programme}"]'))
    page.select_option("#a_schedule", index=1)
    page.click("#nextBtn"); page.wait_for_selector("#feeCalc .fee-box")
    if award:
        page.check('input[name="awardRequest"][value="excellence"]')
    page.check("#a_declare")
    page.click("#submitBtn"); page.wait_for_url("**/apply/done/**"); page.wait_for_selector("#admissionResult")


def pay(page, outcome="success"):
    page.wait_for_selector("#payNow"); page.click("#payNow")
    page.wait_for_url("**/api/payments/simulator/*")
    page.click(f"button[value={outcome}]")
    page.wait_for_url("**/payments/TSCE-ZP-*/" if outcome == "success" else "**/pay/**")


with sync_playwright() as p:
    browser = p.chromium.launch(channel=os.environ.get("E2E_BROWSER", "msedge"), headless=True)
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)

    # Applying needs an account
    page.goto(f"{B}/pages/application.html"); page.wait_for_url("**/apply/"); page.wait_for_selector("#wizardRoot .card")
    check("apply page asks visitors to create an account", "Create an account to apply" in page.inner_text("#wizardRoot"))

    # Register as a parent
    page.goto(f"{B}/account/register/"); page.wait_for_selector("#regForm")
    page.click('label.option-card:has(input[value="parent"])')  # the card is what people click
    page.fill("#rName", "Hajiya Rabi Musa"); page.fill("#rEmail", "rabi.musa@example.com")
    page.fill("#rPhone", "0803 555 1234"); page.fill("#rPw", "Parent-Pass-2026"); page.fill("#rPw2", "Parent-Pass-2026")
    page.click("#regForm button[type=submit]"); page.wait_for_selector("text=Check your email")
    check("registration asks to check email", "rabi.musa@example.com" in page.inner_text("#regRoot"))

    # Can't sign in before verifying
    page.goto(f"{B}/account/login/"); page.fill("#loginEmail", "rabi.musa@example.com"); page.fill("#loginPassword", "Parent-Pass-2026")
    page.click("#loginForm button[type=submit]"); page.wait_for_selector("#loginError .alert")
    check("unverified sign-in refused", "verify your email" in page.inner_text("#loginError").lower())

    link = latest_verification_link("rabi.musa@example.com")
    check("verification email sent (console)", link is not None)
    page.goto(link.replace("http://localhost:8000", B)); page.wait_for_selector("#verifyBtn")
    page.click("#verifyBtn"); page.wait_for_url("**/my-applications/")
    page.wait_for_selector("#maRoot .card")
    check("welcome message after verifying", "Email verified" in page.inner_text("main"))
    check("verified → signed in → My applications", "No applications yet" in page.inner_text("#maRoot"))
    check("parent wording", "Apply for a child" in page.inner_text("#maNew"))

    # Child 1: no award
    apply_for_child(page, "Aisha", "2008-03-01", "fullstack")
    check("step 5: admitted on submit", "admitted" in page.inner_text("#admissionResult").lower())
    page.click("#payNowLink"); page.wait_for_selector("#payNow")
    check("one invoice ₦55,300 (or 50%)", "55,300" in page.inner_text(".checkout-head"))
    pay(page)
    page.wait_for_selector(".success-card")
    body = page.inner_text(".success-card")
    check("programme fee paid → enrolled with student number", "ENROLMENT CONFIRMED" in body.upper() and "TSCE/2026/" in body, body[:300])

    # Child 2: Excellence Award
    page.goto(f"{B}/my-applications/"); page.click("#maNew"); page.wait_for_url("**/apply/1/")
    apply_for_child(page, "Umar", "2007-06-09", "network", award=True)
    check("award applicant: told to bring result", "WAEC/NECO" in page.inner_text("#admissionResult"))
    page.goto(f"{B}/my-applications/"); page.wait_for_selector("#maRoot article")
    cards = page.locator("#maRoot article")
    check("two children listed", cards.count() == 2)
    text = page.inner_text("#maRoot")
    check("child 1 enrolled, child 2 awaiting verification", "Enrolled" in text and "Awaiting Verification" in text)
    umar_no = page.evaluate("fetch('/api/applications').then(r => r.json()).then(a => a.find(x => x.firstName === 'Umar').id)")
    page.goto(f"{B}/pay/{umar_no}/"); page.wait_for_selector("#payRoot .empty")
    check("programme fee blocked until verified", "verification pending" in page.inner_text("#payRoot"))

    # Staff verify the WAEC result in person and approve on the application page
    staff_ctx = browser.new_context(); staff = staff_ctx.new_page(); watch(staff)
    staff.goto(f"{B}/account/login/?role=staff"); staff.fill("#loginEmail", "rabi@tsce.edu.ng"); staff.fill("#loginPassword", "Staff-Pass-2026")
    staff.click("#loginForm button[type=submit]"); staff.wait_for_url("**/staff/")
    staff.goto(f"{B}/staff/applications/{umar_no}/"); staff.wait_for_selector('button[value="award-yes"]')
    staff.fill("#id_note", "Original WAEC seen"); staff.click('button[value="award-yes"]'); staff.wait_for_selector(".toast-msg")
    check("staff approve award → admitted at 50% of tuition + ₦5,000", "₦30,000" in staff.inner_text(".toast-msg"), staff.inner_text(".toast-msg"))
    staff_ctx.close()

    page.goto(f"{B}/my-applications/"); page.wait_for_selector("#maRoot article")
    umar = page.locator("#maRoot article", has_text="Umar")
    check("award approved shown to parent", "Excellence Award approved" in umar.inner_text())
    umar.locator("text=Pay programme fee").click(); page.wait_for_selector("#payNow")
    check("discounted programme fee ₦30,300", "30,300" in page.inner_text(".checkout-head"))
    pay(page)
    page.wait_for_selector(".success-card")
    check("child 2 enrolled", "ENROLMENT CONFIRMED" in page.inner_text(".success-card").upper())
    me = page.evaluate("fetch('/api/auth/me').then(r => r.json()).then(r => r.user)")
    check("account stays a parent account", me["role"] == "parent")
    browser.close()

for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or not detail else f" — {detail[:300]}"))
print("JS errors:", errors or "none")
sys.exit(0 if all(ok for _, ok, _ in results) and not errors else 1)
