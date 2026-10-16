"""Browser test of payment states: admitted → one payment (programme fee incl. application fee) via (simulated) Zainpay → receipt."""
import os
import sys
from urllib.parse import quote

from playwright.sync_api import sync_playwright

B = os.environ.get("E2E_BASE", "http://localhost:8765")
APP1 = quote("TSCE/APP/2026/00001", safe="")
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

    ctx = browser.new_context(); page = ctx.new_page(); watch(page)
    page.goto(f"{B}/pages/payment.html?app={APP1}"); page.wait_for_selector("#payRoot .empty")
    check("signed out: asked to sign in", "Sign in to pay" in page.inner_text("#payRoot"))
    ctx.close()

    ctx = browser.new_context(); page = ctx.new_page(); watch(page)
    login(page, "aisha@example.com")
    page.wait_for_url("**/pages/my-applications.html"); page.wait_for_selector("#maRoot article")
    check("applicant login opens My applications", "TSCE/APP/2026/00001" in page.inner_text("#maRoot"))
    page.click("text=Pay programme fee"); page.wait_for_url("**purpose=programme_fee*"); page.wait_for_selector("#payNow")
    summary = page.inner_text(".order-summary")
    check("one invoice: ₦50,000 + ₦5,000 application fee + ₦300", "5,000" in summary and "50,000" in summary and "55,300" in page.inner_text(".checkout-head"), summary)
    check("simulator clearly labelled", "simulated payments" in page.inner_text(".sandbox-box").lower())
    check("bank transfer only", "Bank transfer" in page.inner_text(".checkout") and "Visa" not in page.inner_text(".checkout"))

    page.click("#payNow"); page.wait_for_url("**/api/payments/simulator/*")
    check("simulated checkout charges ₦55,300", "55,300" in page.inner_text(".amt"))
    page.click("button[value=failed]"); page.wait_for_url("**result=failed*"); page.wait_for_selector("#payNow")
    check("declined: back on the same invoice", "didn't go through" in page.inner_text("#payRoot") and "Application fee" in page.inner_text(".order-summary"))

    page.click("#payNow"); page.wait_for_url("**/api/payments/simulator/*")
    page.click("button[value=success]"); page.wait_for_url("**/pages/success.html?ref=*"); page.wait_for_selector(".success-card")
    body = page.inner_text(".success-card")
    check("enrolled with student number", "ENROLMENT CONFIRMED" in body.upper() and "TSCE/2026/00001" in body, body[:300])
    page.click("#dlReceipt"); page.wait_for_selector(".modal .receipt")
    receipt = page.inner_text(".modal .receipt")
    check("receipt itemises programme + application fee", "50,000" in receipt and "Application fee" in receipt and "55,000" in receipt and "TSCE-ZP-" in receipt and "simulated payment" in receipt, receipt[:400])
    check("receipt: charge explained, not in total", "transaction charge" in receipt and "55,300" not in receipt)
    page.keyboard.press("Escape")
    me = page.evaluate("API.get('auth/me').then(r => r.user)")
    check("self-applicant becomes a student", me["role"] == "student" and me["studentId"] == "TSCE/2026/00001")

    page.goto(f"{B}/pages/payment.html?app={APP1}&purpose=programme_fee"); page.wait_for_selector("#payRoot .empty")
    check("programme fee can't be paid twice", "already paid" in page.inner_text("#payRoot"))
    page.goto(f"{B}/pages/payment.html?app={APP1}&purpose=application_fee"); page.wait_for_selector("#payRoot .empty")
    check("old application-fee links land on the same paid state", "already paid" in page.inner_text("#payRoot"))
    page.goto(f"{B}/pages/my-applications.html"); page.wait_for_selector("#maRoot article")
    check("My applications shows enrolled", "Enrolled" in page.inner_text("#maRoot"))
    page.click("#maRoot >> text=Student portal"); page.wait_for_url("**/student/dashboard.html"); page.wait_for_selector("#view")
    check("student portal opens", page.locator("#sidebar .sb-link").count() > 0)
    paid_ref = page.evaluate("API.get('applications/' + encodeURIComponent('TSCE/APP/2026/00001')).then(a => a.txRef)")
    ctx.close()

    # Applicant 2: abandons checkout → pending + checks; can't see applicant 1's things
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)
    login(page, "musa@example.com")
    page.wait_for_url("**/my-applications.html"); page.click("text=Pay programme fee"); page.wait_for_selector("#payNow")
    page.click("#payNow"); page.wait_for_url("**/api/payments/simulator/*")
    page.click("button[value=cancel]"); page.wait_for_url("**result=pending*"); page.wait_for_selector("#pendingBox")
    check("abandoned: 'confirming' notice", "confirming your payment" in page.inner_text("#pendingBox"))
    page.click("#checkNow"); page.wait_for_selector(".toast >> text=Still processing")
    check("manual check reports still processing", True)
    page.goto(f"{B}/pages/success.html?ref={paid_ref}"); page.wait_for_selector("#successRoot .card")
    check("someone else's confirmation is not shown", "couldn't load" in page.inner_text("#successRoot"))
    page.goto(f"{B}/pages/payment.html?app={APP1}"); page.wait_for_selector("#payRoot .empty")
    check("someone else's invoice is not shown", "Application not found" in page.inner_text("#payRoot"))
    ctx.close()

    # Applicant 3: installments — 50% (+ application fee) to enrol, then the balance
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)
    login(page, "zara@example.com")
    page.wait_for_url("**/my-applications.html"); page.wait_for_selector("#maRoot article")
    check("My applications offers 50% now", "pay 50% now" in page.inner_text("#maRoot").lower() and "30,300" in page.inner_text("#maRoot"))
    page.click("text=Pay programme fee"); page.wait_for_selector("#planPick")
    check("plan choice: full selected by default", "55,300" in page.inner_text(".checkout-head"))
    page.click('label.option-card:has(input[value="half"])')
    check("50% plan: ₦30,000 + ₦300", "30,300" in page.inner_text(".checkout-head") and "30,300" in page.inner_text("#payNow"))
    page.click("#payNow"); page.wait_for_url("**/api/payments/simulator/*")
    check("simulated checkout charges ₦30,300", "30,300" in page.inner_text(".amt"))
    page.click("button[value=success]"); page.wait_for_url("**/pages/success.html?ref=*"); page.wait_for_selector(".success-card")
    body = page.inner_text(".success-card")
    check("1st installment enrols, balance shown", "ENROLMENT CONFIRMED" in body.upper() and "25,000" in body and "1st installment" in body, body[:400])
    page.click("#dlReceipt"); page.wait_for_selector(".modal .receipt")
    check("receipt names the installment", "1st installment" in page.inner_text(".modal .receipt") and "30,000" in page.inner_text(".modal .receipt"))
    page.keyboard.press("Escape")
    page.goto(f"{B}/pages/my-applications.html"); page.wait_for_selector("#maRoot article")
    text = page.inner_text("#maRoot")
    check("My applications: enrolled with balance due", "Enrolled" in text and "Balance due" in text and "25,000" in text, text[:400])
    page.click("text=Pay balance"); page.wait_for_selector("#payNow")
    check("balance invoice ₦25,300, no plan choice", "25,300" in page.inner_text(".checkout-head") and page.locator("#planPick").count() == 0)
    page.click("#payNow"); page.wait_for_url("**/api/payments/simulator/*")
    page.click("button[value=success]"); page.wait_for_url("**/pages/success.html?ref=*"); page.wait_for_selector(".success-card")
    check("balance paid → fully paid", "FULLY PAID" in page.inner_text(".success-card").upper())
    app3 = page.evaluate("API.get('applications/' + encodeURIComponent('TSCE/APP/2026/00003'))")
    check("fees cleared", app3["paymentStatus"] == "Paid" and app3["amountPaid"] == 55000 and app3["balance"] == 0, str(app3)[:200])
    browser.close()

for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or not detail else f" — {detail[:300]}"))
print("JS errors:", errors or "none")
sys.exit(0 if all(ok for _, ok, _ in results) and not errors else 1)
