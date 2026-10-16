"""Browser test: sign-in, roles, redirects, logout, session expiry, forced password change.
Run through e2e/run.sh with setup_auth.py (users: director=1, rabi=2, amina=3)."""
import os
import sys

from playwright.sync_api import sync_playwright

B = os.environ.get("E2E_BASE", "http://localhost:8765")
results, errors = [], []


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))


def login(page, email, pw, remember=True):
    page.goto(f"{B}/account/login/"); page.wait_for_selector("#loginForm")
    page.fill("#loginEmail", email)
    page.fill("#loginPassword", pw)
    if not remember:
        page.uncheck("#loginRemember")
    page.click("#loginForm button[type=submit]")


with sync_playwright() as p:
    browser = p.chromium.launch(channel=os.environ.get("E2E_BROWSER", "msedge"), headless=True)
    ctx = browser.new_context()
    page = ctx.new_page()
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and errors.append(f"console: {m.text} @ {page.url}"))

    # 1. Public home: signed out, no demo chrome
    page.goto(f"{B}/index.html"); page.wait_for_selector("#siteHeader")
    check("no demo chip / explore button", page.locator(".demo-chip, .explore-fab").count() == 0)
    check("portal menu says Portals when signed out", "Portals" in page.inner_text("#portalDrop button"))

    # 2. Login page: demo panel gone; wrong password shows the server message
    page.goto(f"{B}/pages/login.html"); page.wait_for_url("**/account/login/"); page.wait_for_selector("#loginForm")
    check("old login address redirects to the new page", page.url.endswith("/account/login/"))
    check("no demo accounts panel", page.locator(".demo-login, [data-demo]").count() == 0)
    login(page, "rabi@tsce.edu.ng", "wrong-password")
    page.wait_for_selector("#loginError .alert")
    check("wrong password message", "Incorrect email or password" in page.inner_text("#loginError"))
    check("password cleared after failure", page.input_value("#loginPassword") == "")

    # 3. Staff login → staff dashboard
    login(page, "rabi@tsce.edu.ng", "Staff-Pass-2026")
    page.wait_for_url("**/staff/"); page.wait_for_selector("#userBtn")
    check("topbar shows real name", "Rabi" in page.inner_text("#userBtn") and "Rabi Isa" in page.inner_text(".sb-user"))
    check("no demo pill", page.locator(".demo-pill").count() == 0)
    check("settings hidden for non-admin", page.locator('.menu-list a[href="/staff/settings/"]').count() == 0)

    # 4. Staff opening a student page is sent back to the staff portal
    page.goto(f"{B}/pages/student/dashboard.html"); page.wait_for_url("**/staff/")
    check("staff blocked from student portal", page.url.endswith("/staff/"))
    page.goto(f"{B}/my-applications/"); page.wait_for_url("**/staff/")
    check("staff kept out of applicant pages", page.url.endswith("/staff/"))

    # 5. Change password from the user menu
    page.click("#userBtn"); page.click("#umPassword"); page.wait_for_selector("#id_old_password")
    page.fill("#id_old_password", "Staff-Pass-2026"); page.fill("#id_new_password1", "Staff-Pass-2027"); page.fill("#id_new_password2", "Staff-Pass-2027")
    page.click("main button[type=submit]"); page.wait_for_url("**/staff/")
    check("staff changed password", "password has been changed" in page.inner_text("#view"))

    # 6. Logout; signed-out portal redirects to login with ?next, which is honoured
    page.click("#userBtn"); page.click("#umLogout"); page.wait_for_url("**/account/login/?out=1")
    check("signed out notice", "signed out" in page.inner_text("main"))
    page.goto(f"{B}/staff/payments/"); page.wait_for_url("**/account/login/?**")
    check("signed-out portal redirects with next", "next=%2Fstaff%2Fpayments%2F" in page.url)
    page.fill("#loginEmail", "rabi@tsce.edu.ng"); page.fill("#loginPassword", "Staff-Pass-2027")
    page.click("#loginForm button[type=submit]"); page.wait_for_url("**/staff/payments/")
    check("login honours next=", page.url.endswith("/staff/payments/"))

    # 7. Session dies mid-use → the next page load asks to sign in again
    ctx.clear_cookies()
    page.goto(f"{B}/staff/applications/")
    page.wait_for_url("**/account/login/?**")
    check("expired session redirects to login", "/account/login/" in page.url)

    # 8. Admin resets the student's password; student must change it
    login(page, "director@tsce.edu.ng", "Director-Pass-2026")
    page.wait_for_url("**/staff/")
    check("admin sees Settings in menu", page.locator('.menu-list a[href="/staff/settings/"]').count() == 1)
    temp = page.evaluate("""fetch('/api/staff/users/3/reset-password', {method: 'POST', headers: {'X-CSRFToken':
        document.cookie.split('; ').find(c => c.startsWith('csrftoken=')).split('=')[1]}}).then(r => r.json()).then(r => r.temporaryPassword)""")
    check("admin got a temporary password", temp and len(temp) == 10)
    page.click("#userBtn"); page.click("#umLogout"); page.wait_for_url("**/account/login/?out=1")
    login(page, "amina@example.com", temp)
    page.wait_for_url("**/account/password/"); page.wait_for_selector("#id_old_password")
    check("forced to choose a new password", "choose a new password" in page.inner_text("main").lower())
    page.goto(f"{B}/my-applications/"); page.wait_for_url("**/account/password/?next=*")
    check("can't skip the password change", "/account/password/" in page.url)
    page.fill("#id_old_password", temp); page.fill("#id_new_password1", "Student-Pass-2027"); page.fill("#id_new_password2", "Student-Pass-2027")
    page.click("main button[type=submit]"); page.wait_for_url("**/my-applications/")
    me = page.evaluate("fetch('/api/auth/me').then(r => r.json()).then(r => r.user)")
    check("mustChangePassword cleared", me["mustChangePassword"] is False and me["role"] == "student")

    # 9. Remember-me off → browser-session cookie
    page.click("#maLogout"); page.wait_for_url("**/account/login/?out=1")
    login(page, "amina@example.com", "Student-Pass-2027", remember=False)
    page.wait_for_url("**/my-applications/")
    sess = [c for c in ctx.cookies() if c["name"] == "sessionid"][0]
    check("remember-me off gives a browser-session cookie", sess["expires"] == -1, str(sess["expires"]))
    check("session cookie is httpOnly", sess["httpOnly"])
    browser.close()

for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or not detail else f" — {detail[:200]}"))
print("JS errors:", errors or "none")
sys.exit(0 if all(ok for _, ok, _ in results) and not errors else 1)
