"""Browser test of the server-rendered payment pages: invoice (full / 50%) → simulated Zainpay → confirmation → receipt."""
import os
import sys

from playwright.sync_api import sync_playwright

B = os.environ.get("E2E_BASE", "http://localhost:8765")
APP1, APP2, APP3 = "TSCE/APP/2026/00001", "TSCE/APP/2026/00002", "TSCE/APP/2026/00003"
results, errors = [], []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


def watch(page):
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e} @ {page.url}"))
    page.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and errors.append(f"console: {m.text} @ {page.url}"))


def login(page, email, pw="Applicant-Pass-2026"):
    page.goto(f"{B}/account/login/"); page.wait_for_selector("#loginForm")
    page.fill("#loginEmail", email); page.fill("#loginPassword", pw)
    page.click("#loginForm button[type=submit]")


def simulate(page, outcome):
    page.click("#payNow"); page.wait_for_url("**/api/payments/simulator/*")
    amount = page.inner_text(".amt")
    page.click(f"button[value={outcome}]")
    return amount


with sync_playwright() as p:
    browser = p.chromium.launch(channel=os.environ.get("E2E_BROWSER", "msedge"), headless=True)

    ctx = browser.new_context(); page = ctx.new_page(); watch(page)
    page.goto(f"{B}/pay/{APP1}/"); page.wait_for_url("**/account/login/?next=*")
    check("signed out: asked to sign in", page.locator("#loginForm").count() == 1)
    ctx.close()

    # Applicant 1: declined, then pays in full
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)
    login(page, "aisha@example.com")
    page.wait_for_url("**/my-applications/"); page.wait_for_selector("#maRoot article")
    check("applicant login opens My applications", APP1 in page.inner_text("#maRoot"))
    page.click("text=Pay programme fee"); page.wait_for_selector("#payNow")
    summary = page.inner_text(".order-summary")
    check("invoice: ₦50,000 + ₦5,000 application fee, both options", "50,000" in summary and "5,000" in summary
          and "55,300" in page.inner_text("#planPick") and "30,300" in page.inner_text("#planPick"), summary)
    check("simulator clearly labelled", "simulated payments" in page.inner_text(".sandbox-box").lower())
    check("bank transfer only", "Bank transfer" in page.inner_text(".checkout") and "Visa" not in page.inner_text(".checkout"))
    check("full is ticked by default", page.is_checked('#planPick input[value="full"]'))

    check("simulated checkout charges ₦55,300", "55,300" in simulate(page, "failed"))
    page.wait_for_url("**/pay/**failed=*"); page.wait_for_selector("#payNow")
    check("declined: back on the same invoice", "didn't go through" in page.inner_text("#payRoot"))

    simulate(page, "success")
    page.wait_for_url("**/payments/TSCE-ZP-*/"); page.wait_for_selector(".success-card")
    body = page.inner_text(".success-card")
    check("enrolled with student number", "ENROLMENT CONFIRMED" in body.upper() and "TSCE/2026/00001" in body, body[:300])
    paid_url = page.url
    page.click("#dlReceipt"); page.wait_for_selector("#receipt")
    receipt = page.inner_text("#receipt")
    check("receipt itemises programme + application fee", "50,000" in receipt and "Application fee" in receipt
          and "55,000" in receipt and "TSCE-ZP-" in receipt and "simulated payment" in receipt, receipt[:400])
    check("receipt: charge explained, not in total", "transaction charge" in receipt and "55,300" not in receipt)
    me = page.evaluate("fetch('/api/auth/me').then(r => r.json()).then(r => r.user)")
    check("self-applicant becomes a student", me["role"] == "student" and me["studentId"] == "TSCE/2026/00001")
    page.goto(f"{B}/pay/{APP1}/"); page.wait_for_selector("#payRoot .empty")
    check("programme fee can't be paid twice", "already paid" in page.inner_text("#payRoot"))
    page.goto(f"{B}/pages/payment.html?app={APP1}&purpose=application_fee"); page.wait_for_selector("#payRoot .empty")
    check("old payment links land on the same paid state", "already paid" in page.inner_text("#payRoot"))
    page.goto(f"{B}/my-applications/"); page.wait_for_selector("#maRoot article")
    check("My applications shows enrolled + receipt", "Enrolled" in page.inner_text("#maRoot") and "Confirmation" in page.inner_text("#maRoot"))
    ctx.close()

    # Applicant 2: abandons checkout → "confirming" page that re-checks; can't see applicant 1's things
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)
    login(page, "musa@example.com")
    page.wait_for_url("**/my-applications/"); page.click("text=Pay programme fee"); page.wait_for_selector("#payNow")
    simulate(page, "cancel")
    page.wait_for_url("**/payments/*/?check=1"); page.wait_for_selector("#pendingBox")
    check("abandoned: 'confirming' notice", "confirming your payment" in page.inner_text("#pendingBox"))
    check("confirming page refreshes itself", page.locator('meta[http-equiv="refresh"]').count() == 1)
    page.click("#checkNow"); page.wait_for_selector("#pendingBox")
    check("manual check reports still processing", "hasn't confirmed this payment yet" in page.inner_text("main"))
    res = page.goto(paid_url)
    check("someone else's confirmation is not shown", res.status == 404)
    res = page.goto(f"{B}/pay/{APP1}/")
    check("someone else's invoice is not shown", res.status == 404)
    ctx.close()

    # Applicant 3: installments — 50% (+ application fee) to enrol, then the balance
    ctx = browser.new_context(); page = ctx.new_page(); watch(page)
    login(page, "zara@example.com")
    page.wait_for_url("**/my-applications/"); page.wait_for_selector("#maRoot article")
    check("My applications offers 50% now", "pay 50% now" in page.inner_text("#maRoot").lower() and "30,300" in page.inner_text("#maRoot"))
    page.click("text=or pay 50% now"); page.wait_for_selector("#planPick")
    check("the 50% link pre-ticks the 50% option", page.is_checked('#planPick input[value="half"]'))
    check("simulated checkout charges ₦30,300", "30,300" in simulate(page, "success"))
    page.wait_for_url("**/payments/TSCE-ZP-*/"); page.wait_for_selector(".success-card")
    body = page.inner_text(".success-card")
    check("1st installment enrols, balance shown", "ENROLMENT CONFIRMED" in body.upper() and "25,000" in body and "1st installment" in body, body[:400])
    page.click("#dlReceipt"); page.wait_for_selector("#receipt")
    check("receipt names the installment", "1st installment" in page.inner_text("#receipt") and "30,000" in page.inner_text("#receipt"))
    page.goto(f"{B}/my-applications/"); page.wait_for_selector("#maRoot article")
    text = page.inner_text("#maRoot")
    check("My applications: enrolled with balance due", "Enrolled" in text and "Balance due" in text and "25,000" in text, text[:400])
    page.click("text=Pay balance"); page.wait_for_selector("#payNow")
    check("balance invoice ₦25,300, no plan choice", "25,300" in page.inner_text(".checkout-head") and page.locator("#planPick").count() == 0)
    simulate(page, "success")
    page.wait_for_url("**/payments/TSCE-ZP-*/"); page.wait_for_selector(".success-card")
    check("balance paid → fully paid", "FULLY PAID" in page.inner_text(".success-card").upper())
    app3 = page.evaluate(f"fetch('/api/applications/' + encodeURIComponent('{APP3}')).then(r => r.json())")
    check("fees cleared", app3["paymentStatus"] == "Paid" and app3["amountPaid"] == 55000 and app3["balance"] == 0, str(app3)[:200])
    browser.close()

for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or not detail else f" — {detail[:300]}"))
print("JS errors:", errors or "none")
sys.exit(0 if all(ok for _, ok, _ in results) and not errors else 1)
