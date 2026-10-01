/* ==========================================================================
   TSCE — Authentication (server sessions)
   Roles: applicant · student · staff · admin
   The session lives in an httpOnly cookie set by Django. On every page the
   router calls Auth.load() once (GET /api/auth/me); after that Auth.current()
   returns the cached user synchronously, as the rest of the code expects:
     { id, email, name, role, isAdmin, studentId, staffId, applicationId, mustChangePassword }
   ========================================================================== */

const Auth = (() => {
    let user = null;

    /** Fetches the signed-in user (null for visitors). Never throws. */
    async function load() {
        try { user = (await API.get("auth/me")).user; }
        catch (e) { user = null; if (e.isNetwork) console.warn("TSCE: server unreachable — continuing signed out."); }
        return user;
    }
    const current = () => user;
    const isAdmin = () => !!user?.isAdmin;

    async function login(email, password, { remember = true } = {}) {
        try {
            user = (await API.post("auth/login", { email: String(email).trim(), password, remember })).user;
            return { ok: true, user };
        } catch (e) {
            return { ok: false, error: e.message, code: e.code };
        }
    }
    async function logout(redirect = true) {
        try { await API.post("auth/logout"); } catch (e) { /* already signed out */ }
        user = null;
        if (redirect) location.href = UI.url("pages/login.html?out=1");
    }
    async function changePassword(currentPassword, newPassword) {
        user = (await API.post("auth/change-password", { currentPassword, newPassword })).user;
        return user;
    }

    function homeFor(role, s = current()) {
        if (role === "student") return UI.url("pages/student/dashboard.html");
        if (role === "staff" || role === "admin") return UI.url("pages/staff/dashboard.html");
        if (role === "applicant" || role === "parent") return UI.url("pages/my-applications.html");
        return UI.url("index.html");
    }
    function loginUrl(portal) {
        return UI.url(`pages/login.html?role=${portal}&next=${encodeURIComponent(location.pathname.split("/").slice(-2).join("/"))}`);
    }
    /** Guards a portal page. portal: "student" | "staff". Returns the user or redirects. */
    function require(portal) {
        const allowed = portal === "student" ? ["student"] : ["staff", "admin"];
        if (!user) { location.replace(loginUrl(portal)); return null; }
        if (!allowed.includes(user.role)) { location.replace(homeFor(user.role, user)); return null; }
        return user;
    }
    /** Shown when an admin has reset the password: the user must pick a new one. */
    function forcePasswordChange() {
        const m = UI.modal({
            title: "Choose a new password", subtitle: "Your password was reset by the TSCE admin office. Set your own password to continue.",
            size: "sm", dismissible: false,
            body: `<form id="fpcForm" class="form-grid" novalidate style="grid-template-columns:1fr">
                <div class="field"><label for="fpc0">Temporary password <span class="req">*</span></label><input id="fpc0" name="currentPassword" type="password" class="input" required autocomplete="current-password"></div>
                <div class="field"><label for="fpc1">New password <span class="req">*</span></label><input id="fpc1" name="newPassword" type="password" class="input" required minlength="8" autocomplete="new-password"></div>
                <div class="field"><label for="fpc2">Confirm new password <span class="req">*</span></label><input id="fpc2" type="password" class="input" required data-match="fpc1" autocomplete="new-password"></div>
                <p class="hint">At least 8 characters. Avoid common words or only numbers.</p></form>`,
            footer: `<button class="btn btn-ghost" id="fpcOut">Log out</button><button class="btn btn-primary" id="fpcSave">Save password</button>`
        });
        const f = UI.$("#fpcForm", m.el);
        UI.liveValidate(f);
        UI.$("#fpcOut", m.el).onclick = () => logout();
        const save = async (e) => {
            e?.preventDefault();
            if (!UI.validate(f)) return;
            const btn = UI.$("#fpcSave", m.el);
            btn.disabled = true;
            try {
                await changePassword(UI.$("#fpc0", m.el).value, UI.$("#fpc1", m.el).value);
                m.close();
                UI.toast("Password updated", "Use your new password next time you sign in.", "success");
            } catch (err) {
                if (!API.showFieldErrors(f, err)) UI.toast("Couldn't update password", err.message, "error");
            } finally { btn.disabled = false; }
        };
        f.onsubmit = save;
        UI.$("#fpcSave", m.el).onclick = save;
    }

    // Any 401 on a portal page means the session ended (expired, or signed out elsewhere).
    document.addEventListener("api:unauthorized", () => {
        const portal = document.body.dataset.portal;
        if (portal) location.replace(loginUrl(portal));
    });

    return { load, current, isAdmin, login, logout, changePassword, homeFor, require, forcePasswordChange };
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
        UI.$("#loginError").innerHTML = "";
        const r = await Auth.login(emailI.value, pwI.value, { remember: UI.$("#loginRemember").checked });
        if (!r.ok) {
            btn.disabled = false; btn.innerHTML = `Sign in <i class="fa-solid fa-arrow-right"></i>`;
            UI.$("#loginError").innerHTML = `<div class="alert danger mb-2" role="alert"><i class="fa-solid fa-circle-exclamation"></i><p>${UI.esc(r.error)}</p></div>`;
            if (r.code === "invalid_credentials") { pwI.value = ""; pwI.focus(); }
            return;
        }
        const portalOf = (x) => x === "student" ? "student" : x === "applicant" ? "applicant" : "staff";
        if (portalOf(r.user.role) !== role && r.user.role !== "applicant") UI.toast("Redirecting", `This is a ${r.user.role} account — opening the correct portal.`, "info");
        const next = UI.param("next");
        location.href = next && next.startsWith(r.user.role === "student" ? "student/" : "staff/") ? UI.url("pages/" + next) : Auth.homeFor(r.user.role, r.user);
    });

    UI.$("#forgotPw").addEventListener("click", () => {
        UI.modal({
            title: "Forgot your password?", subtitle: "The TSCE admin office can reset it for you.", size: "sm",
            body: `<p>Contact the admin office with the email address you registered with. They will give you a temporary password, and you'll choose a new one when you sign in.</p>
                <ul class="list mt-2">${TSCE_FLYER.phones.map((p) => `<li class="list-item"><span class="icon-tile"><i class="fa-solid fa-phone"></i></span><div class="grow"><strong><a href="tel:${p.replace(/\s/g, "")}">${p}</a></strong><small>Mon–Fri, 8:00am – 5:00pm</small></div></li>`).join("")}
                <li class="list-item"><span class="icon-tile cyan"><i class="fa-solid fa-envelope"></i></span><div class="grow"><strong><a href="mailto:${TSCE_FLYER.email}">${TSCE_FLYER.email}</a></strong><small>Email</small></div></li></ul>`,
            footer: `<button class="btn btn-primary" data-close>OK</button>`
        });
    });
};

/* ---------------- Register ---------------- */
Pages["register"] = function () {
    const f = UI.$("#regForm");
    const s = Auth.current();
    if (s) {
        UI.$("#regRoot").insertAdjacentHTML("afterbegin", `<div class="alert success mt-2"><i class="fa-solid fa-circle-check"></i><p>You're signed in as <b>${UI.esc(s.name)}</b>. <a href="${Auth.homeFor(s.role, s)}">Continue →</a></p></div>`);
    }
    const setType = () => {
        const parent = UI.$('input[name="accountType"]:checked', f).value === "parent";
        UI.$("#rNameLbl").innerHTML = `${parent ? "Your full name (parent / guardian)" : "Your full name"} <span class="req">*</span>`;
    };
    UI.$$('input[name="accountType"]', f).forEach((r) => r.addEventListener("change", setType));
    setType();
    UI.liveValidate(f);

    function sent(email) {
        UI.$("#regRoot").innerHTML = `<a href="../index.html" class="small muted"><i class="fa-solid fa-arrow-left"></i> Back to website</a>
            <div class="empty"><div class="empty-icon"><i class="fa-solid fa-envelope-circle-check"></i></div>
            <h3>Check your email</h3><p class="muted">We've sent a verification link to <b>${UI.esc(email)}</b>. Open it to activate your account, then you can apply.</p>
            <p class="small muted">Can't find it? Check your spam folder, or <button class="link-btn" id="resend">send it again</button>.</p>
            <a class="btn btn-ghost mt-2" href="login.html?role=student">Go to sign in</a></div>`;
        UI.$("#resend").onclick = async () => {
            try { await API.post("auth/resend-verification", { email }); UI.toast("Link sent", `If ${email} still needs verifying, a new link is on its way.`, "success"); }
            catch (e) { UI.toast("Couldn't resend", e.message, "error"); }
        };
    }
    f.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!UI.validate(f)) return;
        const btn = UI.$("button[type=submit]", f);
        btn.disabled = true; btn.innerHTML = `<span class="spinner"></span> Creating account…`;
        const d = UI.formData(f);
        try {
            const r = await API.post("auth/register", { accountType: d.accountType, fullName: d.fullName, email: d.email, phone: d.phone, password: d.password });
            sent(r.email);
        } catch (err) {
            btn.disabled = false; btn.innerHTML = `Create account <i class="fa-solid fa-arrow-right"></i>`;
            if (!API.showFieldErrors(f, err)) UI.toast("Couldn't create account", err.message, "error");
        }
    });
};

/* ---------------- Verify email (link from the registration email) ---------------- */
Pages["verify-email"] = async function () {
    const box = UI.$("#verifyRoot");
    const back = `<a href="../index.html" class="small muted"><i class="fa-solid fa-arrow-left"></i> Back to website</a>`;
    function resendForm(message) {
        box.innerHTML = `${back}<h1 class="mt-3">Verify your email</h1>
            <div class="alert warning mb-2"><i class="fa-solid fa-triangle-exclamation"></i><p>${UI.esc(message)}</p></div>
            <form id="rvForm" novalidate><div class="field mb-2"><label for="rvEmail">Email address</label><input id="rvEmail" type="email" class="input" required autocomplete="email"></div>
            <button class="btn btn-primary btn-block">Send a new link</button></form>
            <p class="small muted mt-3">Already verified? <a href="login.html?role=student">Sign in</a></p>`;
        const f = UI.$("#rvForm");
        f.onsubmit = async (e) => {
            e.preventDefault(); if (!UI.validate(f)) return;
            try { await API.post("auth/resend-verification", { email: UI.$("#rvEmail").value }); UI.toast("Link sent", "If that account still needs verifying, a new link is on its way.", "success"); }
            catch (err) { UI.toast("Couldn't send", err.message, "error"); }
        };
    }
    const token = UI.param("token");
    if (!token) return resendForm("Open the verification link from your email, or request a new one below.");
    box.innerHTML = `${back}<div class="empty"><span class="spinner"></span><p class="muted mt-2">Verifying your email…</p></div>`;
    try {
        const r = await API.post("auth/verify-email", { token });
        if (r.alreadyVerified) {
            box.innerHTML = `${back}<div class="empty"><div class="empty-icon"><i class="fa-solid fa-circle-check"></i></div><h3>Your email is already verified</h3><p class="muted">Sign in to continue.</p><a class="btn btn-primary" href="login.html?role=student">Sign in</a></div>`;
            return;
        }
        box.innerHTML = `${back}<div class="empty"><div class="empty-icon"><i class="fa-solid fa-circle-check"></i></div><h3>Email verified</h3><p class="muted">Welcome, ${UI.esc(r.user.name.split(" ")[0])}! Taking you to your applications…</p></div>`;
        setTimeout(() => location.replace(Auth.homeFor(r.user.role, r.user)), 1200);
    } catch (err) {
        resendForm(err.message);
    }
};
