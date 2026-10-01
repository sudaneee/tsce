/* ==========================================================================
   TSCE — Authentication (simulated, role-based)
   Roles: applicant · student · staff · admin
   BACKEND INTEGRATION POINT: replace login() with POST /api/auth/login
   returning a signed session token (httpOnly cookie). Never store real
   passwords in the browser — this is demo-only.
   ========================================================================== */

const Auth = (() => {
    const DEMO = {
        student: { email: "amina.yusuf@example.com", password: "student123" },
        student2: { email: "muhammad.ibrahim@example.com", password: "student123" },
        staff: { email: "admin@tsce.edu.ng", password: "admin123" },
        officer: { email: "admissions@tsce.edu.ng", password: "staff123" }
    };

    function login(email, password) {
        const user = DB.first("users", (u) => u.email.toLowerCase() === String(email).trim().toLowerCase());
        if (!user || user.password !== password) return { ok: false, error: "Incorrect email or password. Please check your details and try again." };
        if (user.disabled) return { ok: false, error: "This account has been disabled. Contact the TSCE admin office." };
        const session = { email: user.email, role: user.role, name: user.name, studentId: user.studentId || null, staffId: user.staffId || null, applicationId: user.applicationId || null, at: new Date().toISOString() };
        DB.session.set(session);
        return { ok: true, user: session };
    }
    const current = () => DB.session.get();
    function logout(redirect = true) {
        DB.session.clear();
        if (redirect) location.href = UI.url("pages/login.html?out=1");
    }
    function homeFor(role, s = current()) {
        if (role === "student") return UI.url("pages/student/dashboard.html");
        if (role === "staff" || role === "admin") return UI.url("pages/staff/dashboard.html");
        if (role === "applicant") return UI.url(`pages/payment.html?app=${encodeURIComponent(s?.applicationId || "")}`);
        return UI.url("index.html");
    }
    /** Guards a portal page. portal: "student" | "staff". Returns session or redirects. */
    function require(portal) {
        const s = current();
        const allowed = portal === "student" ? ["student"] : ["staff", "admin"];
        if (!s) { location.replace(UI.url(`pages/login.html?role=${portal}&next=${encodeURIComponent(location.pathname.split("/").slice(-2).join("/"))}`)); return null; }
        if (!allowed.includes(s.role)) { location.replace(homeFor(s.role, s)); return null; }
        return s;
    }
    const isAdmin = () => current()?.role === "admin";
    function demo(which) {
        const d = DEMO[which];
        const r = login(d.email, d.password);
        if (r.ok) location.href = homeFor(r.user.role);
    }
    /** Logs a freshly-activated student in (used after successful payment). */
    function signInAs(email) {
        const u = DB.first("users", (x) => x.email === email);
        if (!u) return false;
        DB.session.set({ email: u.email, role: u.role, name: u.name, studentId: u.studentId || null, staffId: null, at: new Date().toISOString() });
        return true;
    }

    return { DEMO, login, current, logout, homeFor, require, isAdmin, demo, signInAs };
})();

/* ---------------- Login page ---------------- */
Pages["login"] = function () {
    const form = UI.$("#loginForm");
    const roleBtns = UI.$$(".role-switch button");
    const emailI = UI.$("#loginEmail"), pwI = UI.$("#loginPassword");
    let role = UI.param("role") === "staff" ? "staff" : "student";

    const s = Auth.current();
    if (s && !UI.param("out")) {
        UI.$("#alreadyIn").innerHTML = `<div class="alert success mb-2"><i class="fa-solid fa-circle-check"></i><p>You are signed in as <b>${UI.esc(s.name)}</b>. <a href="${Auth.homeFor(s.role, s)}">Continue to your portal →</a></p></div>`;
    }
    if (UI.param("out")) UI.toast("Signed out", "You have been signed out securely.", "success");

    function setRole(r) {
        role = r;
        roleBtns.forEach((b) => { const on = b.dataset.role === r; b.classList.toggle("active", on); b.setAttribute("aria-pressed", on); });
        UI.$("#loginTitle").textContent = r === "staff" ? "Staff Portal" : "Student Portal";
        UI.$("#loginSub").textContent = r === "staff" ? "Manage admissions, students, payments and reports." : "Access your programme, results, payments and certificate.";
        emailI.placeholder = r === "staff" ? "you@tsce.edu.ng" : "you@example.com";
    }
    roleBtns.forEach((b) => b.addEventListener("click", () => setRole(b.dataset.role)));
    setRole(role);

    UI.$("#togglePw").addEventListener("click", (e) => {
        const show = pwI.type === "password";
        pwI.type = show ? "text" : "password";
        e.currentTarget.innerHTML = `<i class="fa-solid ${show ? "fa-eye-slash" : "fa-eye"}"></i>`;
        e.currentTarget.setAttribute("aria-label", show ? "Hide password" : "Show password");
    });

    UI.liveValidate(form);
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!UI.validate(form)) return;
        const btn = UI.$("button[type=submit]", form);
        btn.disabled = true; btn.innerHTML = `<span class="spinner"></span> Signing in…`;
        await UI.sleep(650);
        const r = Auth.login(emailI.value, pwI.value);
        if (!r.ok) {
            btn.disabled = false; btn.innerHTML = `Sign in <i class="fa-solid fa-arrow-right"></i>`;
            UI.$("#loginError").innerHTML = `<div class="alert danger mb-2" role="alert"><i class="fa-solid fa-circle-exclamation"></i><p>${r.error}</p></div>`;
            return;
        }
        const portalOf = (x) => x === "student" ? "student" : x === "applicant" ? "applicant" : "staff";
        if (portalOf(r.user.role) !== role && r.user.role !== "applicant") UI.toast("Redirecting", `This is a ${r.user.role} account — opening the correct portal.`, "info");
        const next = UI.param("next");
        location.href = next && next.startsWith(r.user.role === "student" ? "student/" : "staff/") ? UI.url("pages/" + next) : Auth.homeFor(r.user.role, r.user);
    });

    UI.$$("[data-demo]").forEach((b) => b.addEventListener("click", () => {
        const d = Auth.DEMO[b.dataset.demo];
        setRole(b.dataset.demo.startsWith("student") ? "student" : "staff");
        emailI.value = d.email; pwI.value = d.password;
        form.requestSubmit();
    }));
    UI.$("#forgotPw").addEventListener("click", () => {
        const m = UI.modal({
            title: "Reset your password", subtitle: "We'll send a secure reset link to your email.", size: "sm",
            body: `<div class="field"><label for="fpEmail">Email address</label><input id="fpEmail" type="email" class="input" required value="${UI.esc(emailI.value)}"></div>`,
            footer: `<button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-primary" id="fpSend">Send reset link</button>`
        });
        UI.$("#fpSend", m.el).onclick = () => { if (!UI.validate(m.body)) return; m.close(); UI.toast("Reset link sent", "Demo mode: no email is actually sent.", "success"); };
    });
};
