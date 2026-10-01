"""Browser test for Phase 3 (public site + application) against a dev server on :8765."""
import os
import sys

from playwright.sync_api import sync_playwright

B = os.environ.get("E2E_BASE", "http://localhost:8765")
PDF = os.path.join(os.environ.get("CACHE_DIR", "."), "..", "waec-test.pdf")
open(PDF, "wb").write(b"%PDF-1.4\n% e2e test\n")
results, errors = [], []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


def watch(page):
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e} @ {page.url}"))
    page.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and errors.append(f"console: {m.text} @ {page.url}"))


def fill_application(page, email, password="Zaria-Campus-2026", signed_in=False):
    page.goto(f"{B}/pages/application.html?programme=fullstack"); page.wait_for_selector("#a_first")
    page.fill("#a_first", "Aisha"); page.fill("#a_last", "Garba")
    page.select_option("#a_gender", "Female"); page.fill("#a_dob", "2002-05-14")
    page.fill("#a_phone", "0803 123 4567")
    if not signed_in:
        page.fill("#a_email", email)
    page.select_option("#a_state", "Kaduna"); page.fill("#a_address", "12 Samaru Road, Zaria"); page.fill("#a_lga", "Zaria")
    page.click("#nextBtn"); page.wait_for_selector("#a_qual:visible")
    page.select_option("#a_qual", "OND"); page.fill("#a_grad", "2023"); page.fill("#a_inst", "Nuhu Bamalli Polytechnic")
    page.select_option("#a_waec", "Available"); page.fill("#a_waecYear", "2022"); page.fill("#a_numAs", "6")
    page.set_input_files("#a_file", PDF)
    page.click("#nextBtn"); page.wait_for_selector("#a_schedule:visible")
    page.select_option("#a_schedule", index=1)
    page.click("#nextBtn"); page.wait_for_selector("#discountList .discount-card")
    if not signed_in:
        page.fill("#a_password", password); page.fill("#a_password2", password)
    page.check("#a_declare")


with sync_playwright() as p:
    browser = p.chromium.launch(channel=os.environ.get("E2E_BROWSER", "msedge"), headless=True)

    # ---------- visitor ----------
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)
    page.goto(f"{B}/index.html"); page.wait_for_selector("#featuredProgs .prog-card")
    check("home: featured programmes from API", page.locator("#featuredProgs .prog-card").count() == 6)
    check("home: demo stats hidden", not page.is_visible(".stats-band"))
    check("home: demo testimonials hidden", not page.is_visible("#testiTitle"))
    bar = page.inner_text(".announce-bar")
    check("header: cohort date from server", "Monday, 12 October 2026" in bar, bar)
    check("header: no early-bird promise after deadline", "% off" not in bar, bar)

    page.goto(f"{B}/pages/programmes.html"); page.wait_for_selector("#progGrid .prog-card")
    check("catalogue: 11 programmes", page.locator("#progGrid .prog-card").count() == 11)
    page.click('[data-prog="fullstack"]'); page.wait_for_selector(".pd-facts")
    facts = page.inner_text(".pd-facts")
    check("detail: seats + start date", "40 / 40" in facts and "12 Oct 2026" in facts, facts)
    check("detail: no empty instructor line", "Lead instructor" not in page.inner_text(".modal"))
    page.keyboard.press("Escape")

    page.goto(f"{B}/pages/admissions.html"); page.wait_for_selector("#feeTable tr")
    check("admissions: fee table rows", page.locator("#feeTable tr").count() == 11)

    # Application: client-side validation, then a real submission
    page.goto(f"{B}/pages/application.html"); page.wait_for_selector("#a_first")
    check("application: autofill demo button removed", page.locator("#autofill").count() == 0)
    page.click("#nextBtn")
    check("application: step 1 requires fields", page.locator(".field.has-error").count() > 3)
    fill_application(page, "aisha.garba@example.com")
    fee = page.inner_text("#feeCalc")
    check("review: no early bird after 1 Oct, ₦50,000", "50,000" in fee and "Early Bird" not in fee, fee)
    check("review: excellence eligible offered", page.locator('input[name="awardRequest"][value="excellence"]:not([disabled])').count() == 1)
    page.check('input[name="awardRequest"][value="excellence"]')
    page.click("#submitBtn")
    page.wait_for_url("**/pages/payment.html?app=*")
    check("submit → payment page with application number", "TSCE%2FAPP%2F2026%2F00001" in page.url, page.url)
    me = page.evaluate("API.get('auth/me').then(r => r.user)")
    check("applicant is signed in", me and me["role"] == "applicant" and me["applicationId"] == "TSCE/APP/2026/00001")
    detail = page.evaluate("API.get('applications/' + encodeURIComponent('TSCE/APP/2026/00001'))")
    check("server stored award request + amount", detail["awardRequest"]["type"] == "excellence" and detail["amountPayable"] == 50000)
    draft = page.evaluate("sessionStorage.getItem('tsce_appDraft')")
    check("draft cleared after submit", draft is None)

    # Signed-in applicant: email locked, no password
    page.goto(f"{B}/pages/application.html"); page.wait_for_selector("#a_email")
    check("signed in: email read-only + prefilled", page.eval_on_selector("#a_email", "e => e.readOnly && e.value === 'aisha.garba@example.com'"))
    check("signed in: password fields hidden", not page.is_visible("#a_password"))
    ctx.close()

    # ---------- another visitor reuses the email with the wrong password ----------
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)
    fill_application(page, "aisha.garba@example.com", password="Wrong-Password-77")
    page.click("#submitBtn"); page.wait_for_selector("#a_password[aria-invalid='true'], .field.has-error #a_password")
    err = page.locator("#a_password").locator("xpath=ancestor::div[contains(@class,'field')][1]").inner_text()
    check("server error shown on password field", "already exists" in err, err)
    check("stays on review step", page.url.endswith("application.html?programme=fullstack"))

    # Contact form
    page.goto(f"{B}/pages/contact.html"); page.wait_for_selector("#contactForm")
    page.fill("#contactForm [name=name]", "Musa Ali"); page.fill("#contactForm [name=email]", "musa@example.com")
    if page.locator("#contactForm [name=phone]").count():
        page.fill("#contactForm [name=phone]", "08061234567")
    if page.locator("#contactForm [name=subject]").count():
        page.fill("#contactForm [name=subject]", "Weekend classes")
    page.fill("#contactForm [name=message]", "Do you have weekend classes for Network Engineering?")
    page.click("#contactForm button[type=submit]"); page.wait_for_selector("text=Message sent")
    check("contact: enquiry sent", True)

    # News
    page.goto(f"{B}/pages/news.html"); page.wait_for_selector("#newsGrid .news-card")
    check("news: published public announcement", "Orientation for new students" in page.inner_text("#newsGrid"))
    page.click("[data-read]"); page.wait_for_selector(".modal >> text=main hall")
    check("news: read more opens", True)

    # Verify
    page.goto(f"{B}/pages/verify.html"); page.wait_for_selector("#verifyForm")
    check("verify: demo sample numbers removed", page.locator("[data-sample]").count() == 0)
    page.fill("#verifyNo", "TSCE/CERT/2026/90001"); page.click("#verifyForm button")
    page.wait_for_selector("text=Certificate verified")
    check("verify: valid certificate", "Bello Musa" in page.inner_text("#verifyResult"))
    page.fill("#verifyNo", "TSCE/CERT/2026/12345"); page.click("#verifyForm button")
    page.wait_for_selector("#verifyResult >> text=No certificate found")
    check("verify: unknown number", True)
    ctx.close()

    # ---------- staff portal still works with catalogue from the API ----------
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)
    page.goto(f"{B}/pages/login.html"); page.fill("#loginEmail", "rabi@tsce.edu.ng"); page.fill("#loginPassword", "Staff-Pass-2026")
    page.click("#loginForm button[type=submit]"); page.wait_for_url("**/staff/dashboard.html"); page.wait_for_timeout(800)
    check("staff dashboard renders", page.locator("#view .kpi, #view .panel").count() > 0)
    ctx.close()
    browser.close()

for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or not detail else f" — {detail[:200]}"))
print("JS errors:", errors or "none")
sys.exit(0 if all(ok for _, ok, _ in results) and not errors else 1)
