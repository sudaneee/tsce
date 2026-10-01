"""Browser test of the public site: catalogue, admissions, application gate, contact, news, verify."""
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


with sync_playwright() as p:
    browser = p.chromium.launch(channel=os.environ.get("E2E_BROWSER", "msedge"), headless=True)
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)

    page.goto(f"{B}/index.html"); page.wait_for_selector("#featuredProgs .prog-card")
    check("home: featured programmes from API", page.locator("#featuredProgs .prog-card").count() == 6)
    check("home: demo stats hidden", not page.is_visible(".stats-band"))
    check("home: demo testimonials hidden", not page.is_visible("#testiTitle"))
    check("home: no Performance Scholarship offer", "Prove your potential" not in page.inner_text("#scholarships"))
    bar = page.inner_text(".announce-bar")
    check("header: cohort date from server", "Monday, 12 October 2026" in bar, bar)
    check("header: no early-bird promise after deadline", "% off" not in bar, bar)

    page.goto(f"{B}/pages/programmes.html"); page.wait_for_selector("#progGrid .prog-card")
    check("catalogue: 11 programmes", page.locator("#progGrid .prog-card").count() == 11)
    page.click('[data-prog="fullstack"]'); page.wait_for_selector(".pd-facts")
    facts = page.inner_text(".pd-facts")
    check("detail: seats + start date", "40 / 40" in facts and "12 Oct 2026" in facts, facts)
    page.keyboard.press("Escape")

    page.goto(f"{B}/pages/admissions.html"); page.wait_for_selector("#feeTable tr")
    check("admissions: fee table rows", page.locator("#feeTable tr").count() == 11)
    text = page.inner_text("main")
    check("admissions: five-step two-fee flow", "Create an account" in text and "Pay the application fee" in text and "Pay the programme fee" in text)
    check("admissions: scholarship removed", "Performance Scholarship" not in text)

    page.goto(f"{B}/pages/application.html"); page.wait_for_selector("#wizardRoot .card")
    check("application requires an account", "Create an account to apply" in page.inner_text("#wizardRoot"))
    page.click("#wizardRoot a.btn-primary"); page.wait_for_url("**/register.html")
    check("register page reachable", page.locator("#regForm").count() == 1)

    page.goto(f"{B}/pages/contact.html"); page.wait_for_selector("#contactForm")
    page.fill("#contactForm [name=name]", "Musa Ali"); page.fill("#contactForm [name=email]", "musa@example.com")
    if page.locator("#contactForm [name=phone]").count():
        page.fill("#contactForm [name=phone]", "08061234567")
    if page.locator("#contactForm [name=subject]").count():
        page.fill("#contactForm [name=subject]", "Weekend classes")
    page.fill("#contactForm [name=message]", "Do you have weekend classes for Network Engineering?")
    page.click("#contactForm button[type=submit]"); page.wait_for_selector("text=Message sent")
    check("contact: enquiry sent", True)

    page.goto(f"{B}/pages/news.html"); page.wait_for_selector("#newsGrid .news-card")
    check("news: published public announcement", "Orientation for new students" in page.inner_text("#newsGrid"))
    page.click("[data-read]"); page.wait_for_selector(".modal >> text=main hall")
    check("news: read more opens", True)

    page.goto(f"{B}/pages/verify.html"); page.wait_for_selector("#verifyForm")
    check("verify: demo sample numbers removed", page.locator("[data-sample]").count() == 0)
    page.fill("#verifyNo", "TSCE/CERT/2026/90001"); page.click("#verifyForm button")
    page.wait_for_selector("text=Certificate verified")
    check("verify: valid certificate", "Bello Musa" in page.inner_text("#verifyResult"))
    page.fill("#verifyNo", "TSCE/CERT/2026/12345"); page.click("#verifyForm button")
    page.wait_for_selector("#verifyResult >> text=No certificate found")
    check("verify: unknown number", True)
    ctx.close()

    # Staff portal still renders with the catalogue from the API
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)
    page.goto(f"{B}/pages/login.html"); page.fill("#loginEmail", "rabi@tsce.edu.ng"); page.fill("#loginPassword", "Staff-Pass-2026")
    page.click("#loginForm button[type=submit]"); page.wait_for_url("**/staff/dashboard.html"); page.wait_for_timeout(800)
    check("staff dashboard renders", page.locator("#view .kpi, #view .panel").count() > 0)
    browser.close()

for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or not detail else f" — {detail[:200]}"))
print("JS errors:", errors or "none")
sys.exit(0 if all(ok for _, ok, _ in results) and not errors else 1)
