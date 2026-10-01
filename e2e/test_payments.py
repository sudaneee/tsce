"""Browser test: invoice → (simulated) Zainpay checkout → callback → success page / receipt."""
import os
import sys
from urllib.parse import quote

from playwright.sync_api import sync_playwright

B = os.environ.get("E2E_BASE", "http://localhost:8765")
APP1 = quote("TSCE/APP/2026/00001", safe="")
APP2 = quote("TSCE/APP/2026/00002", safe="")
results, errors = [], []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


def watch(page):
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e} @ {page.url}"))
    page.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and errors.append(f"console: {m.text} @ {page.url}"))


def login(page, email, pw="Applicant-Pass-2026"):
    page.goto(f"{B}/pages/login.html"); page.wait_for_selector("#loginForm")
    page.fill("#loginEmail", email); page.fill("#loginPassword", pw)
    page.click("#loginForm button[type=submit]")


with sync_playwright() as p:
    browser = p.chromium.launch(channel=os.environ.get("E2E_BROWSER", "msedge"), headless=True)

    # Signed out
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)
    page.goto(f"{B}/pages/payment.html?app={APP1}"); page.wait_for_selector("#payRoot .card")
    check("signed out: asked to sign in", "Sign in to pay" in page.inner_text("#payRoot"))
    ctx.close()

    # Applicant 1: login lands on their invoice
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)
    login(page, "aisha@example.com")
    page.wait_for_url("**/pages/payment.html?app=*"); page.wait_for_selector("#payNow")
    check("applicant login opens their invoice", "TSCE/APP/2026/00001" in page.inner_text(".order-summary"))
    check("invoice total includes ₦300 charge", "50,300" in page.inner_text(".checkout-head"))
    summary = page.inner_text(".order-summary")
    check("invoice itemises fee and charge", "50,000" in summary and "Zainpay transaction charge" in summary and "50,300" in summary)
    check("bank transfer only", "Bank transfer" in page.inner_text(".checkout") and "Visa" not in page.inner_text(".checkout"))
    check("simulator clearly labelled", "simulated payments" in page.inner_text(".sandbox-box").lower())
    check("no fake card form", page.locator("#cardForm, #cNum").count() == 0)

    # Declined
    page.click("#payNow"); page.wait_for_url("**/api/payments/simulator/*")
    check("hosted (simulated) checkout charges fee + ₦300", "50,300" in page.inner_text(".amt"))
    page.click("button[value=failed]"); page.wait_for_url("**/pages/payment.html?*result=failed*"); page.wait_for_selector("#payNow")
    check("declined: back on invoice with explanation", "didn't go through" in page.inner_text("#payRoot"))
    check("declined: badge shows Failed", "Failed" in page.inner_text(".order-summary"))

    # Paid
    page.click("#payNow"); page.wait_for_url("**/api/payments/simulator/*")
    page.click("button[value=success]"); page.wait_for_url("**/pages/success.html?ref=*"); page.wait_for_selector(".success-card")
    body = page.inner_text(".success-card")
    check("success page: verified + student number", "Payment verified" in body and "TSCE/2026/00001" in body, body[:300])
    check("success page: reference format", "TSCE-ZP-" in body)
    page.click("#dlReceipt"); page.wait_for_selector(".modal .receipt")
    receipt = page.inner_text(".modal .receipt")
    check("receipt: amount, ref, sandbox note", "50,000" in receipt and "TSCE-ZP-" in receipt and "simulated payment" in receipt, receipt[:300])
    check("receipt: charge explained, not added to total", "transaction charge" in receipt and "50,300" not in receipt)
    check("receipt: institution from server", "Trust Skills Center of Excellence" in receipt)
    page.keyboard.press("Escape")
    me = page.evaluate("API.get('auth/me').then(r => r.user)")
    check("account upgraded to student", me["role"] == "student" and me["studentId"] == "TSCE/2026/00001")

    page.goto(f"{B}/pages/payment.html?app={APP1}"); page.wait_for_selector("#payRoot .card")
    check("paid invoice can't be paid again", "already been paid" in page.inner_text("#payRoot"))
    page.click("text=View confirmation"); page.wait_for_selector(".success-card")
    check("confirmation reachable later", "APPLICATION SUBMITTED" in page.inner_text(".success-card"))
    page.click("text=Go to Student Portal"); page.wait_for_url("**/student/dashboard.html"); page.wait_for_selector("#view")
    check("student portal opens", page.locator("#sidebar .sb-link").count() > 0)
    paid_ref = page.evaluate("API.get('applications/' + encodeURIComponent('TSCE/APP/2026/00001')).then(a => a.txRef)")
    ctx.close()

    # Applicant 2: abandons checkout → pending → auto/manual checks; can't see applicant 1's payment
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)
    login(page, "musa@example.com")
    page.wait_for_url("**/pages/payment.html?app=*"); page.wait_for_selector("#payNow")
    page.click("#payNow"); page.wait_for_url("**/api/payments/simulator/*")
    page.click("button[value=cancel]"); page.wait_for_url("**/pages/payment.html?*result=pending*"); page.wait_for_selector("#pendingBox")
    check("abandoned: 'confirming' notice", "confirming your payment" in page.inner_text("#pendingBox"))
    page.click("#checkNow"); page.wait_for_selector(".toast >> text=Still processing")
    check("manual check reports still processing", True)

    page.goto(f"{B}/pages/success.html?ref={paid_ref}"); page.wait_for_selector("#successRoot .card")
    check("someone else's confirmation is not shown", "couldn't load" in page.inner_text("#successRoot"))
    page.goto(f"{B}/pages/payment.html?app={APP1}"); page.wait_for_selector("#payRoot .card")
    check("someone else's invoice is not shown", "Application not found" in page.inner_text("#payRoot"))
    ctx.close()
    browser.close()

for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or not detail else f" — {detail[:300]}"))
print("JS errors:", errors or "none")
sys.exit(0 if all(ok for _, ok, _ in results) and not errors else 1)
