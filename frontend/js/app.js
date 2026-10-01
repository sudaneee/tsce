/* ==========================================================================
   TSCE — App bootstrap
   Public layout (announcement bar, header, footer, "
   Platform" presentation mode), public page controllers and the router
   that mounts portal pages. Each HTML page declares:
     <body data-root="../" data-page="programmes" [data-portal="staff"]>
   ========================================================================== */

const App = (() => {
    const NAV = [
        ["index.html", "Home", "fa-house"], ["pages/about.html", "About", "fa-building-columns"], ["pages/programmes.html", "Programmes", "fa-layer-group"],
        ["pages/admissions.html", "Admissions", "fa-door-open"], ["pages/admissions.html#scholarships", "Scholarships", "fa-award"], ["index.html#why", "Why TSCE", "fa-star"],
        ["pages/news.html", "News & Events", "fa-newspaper"], ["pages/contact.html", "Contact", "fa-phone"]
    ];

    function countdownText() {
        if (!Site.cohortDate) return "";
        const target = new Date(`${Site.cohortDate}T08:00:00`);
        const ms = target - Date.now();
        if (ms <= 0) return "Classes are in session";
        const d = Math.floor(ms / 864e5), h = Math.floor(ms / 36e5) % 24;
        return `${d}d ${h}h to kick-off`;
    }

    function header(page) {
        const r = UI.root();
        const eb = Discounts.earlyBirdOpen();
        const bar = `<div class="announce-bar" role="region" aria-label="Announcement"><div class="container">
            <span class="pill">${eb ? "Early bird" : "Enrolling"}</span>
            <span><strong>${TSCE_FLYER.campaign}</strong> <span class="hide-sm">${Site.cohortDate ? `— classes start ${UI.dateLong(Site.day(Site.cohortDate))}` : ""}${eb ? ` · ${Discounts.RULES.earlybird.pct}% off when you pay before ${UI.date(Discounts.deadline(), { day: "numeric", month: "long" })}` : ""}.</span></span>
            <span class="countdown hide-sm"><i class="fa-regular fa-clock"></i> <span id="abCount">${countdownText()}</span></span>
            <a href="${r}pages/application.html">Apply now →</a></div></div>`;
        const isActive = (href) => (href === "index.html" && page === "home") || (href.includes(page + ".html") && !href.includes("#"));
        const links = NAV.map(([h, t]) => `<li><a href="${r}${h}" class="${isActive(h) ? "active" : ""}" ${isActive(h) ? 'aria-current="page"' : ""}>${t}</a></li>`).join("");
        const s = Auth.current();
        const portalItems = `<li><a href="${r}pages/login.html?role=student"><span class="icon-tile"><i class="fa-solid fa-user-graduate"></i></span><span>Student Portal<small>Programme, results & payments</small></span></a></li>
            <li><a href="${r}pages/login.html?role=staff"><span class="icon-tile navy"><i class="fa-solid fa-briefcase"></i></span><span>Staff Portal<small>Admissions, finance & academics</small></span></a></li>
            <li><a href="${r}pages/verify.html"><span class="icon-tile green"><i class="fa-solid fa-shield-halved"></i></span><span>Verify Certificate<small>Check a TSCE certificate</small></span></a></li>`;
        const html = `${bar}<header class="site-header" id="siteHeader"><div class="container nav">
            ${UI.brand(r + "index.html")}
            <nav aria-label="Main navigation"><ul class="nav-links">${links}</ul></nav>
            <div class="nav-actions">
                <div class="nav-drop" id="portalDrop"><button class="btn btn-ghost btn-sm nav-drop-btn" aria-haspopup="true" aria-expanded="false"><i class="fa-regular fa-circle-user"></i> <span class="hide-sm">${s ? "My portal" : "Portals"}</span> <i class="fa-solid fa-chevron-down" style="font-size:.7em"></i></button>
                    <ul class="nav-drop-menu">${s ? `<li><a href="${Auth.homeFor(s.role, s)}"><span class="icon-tile green"><i class="fa-solid fa-arrow-right-to-bracket"></i></span><span>Continue as ${UI.esc(s.name.split(" ")[0])}<small>${s.role} portal</small></span></a></li>` : ""}${portalItems}</ul></div>
                <a class="btn btn-primary btn-sm btn-apply-desktop" href="${r}pages/application.html">Apply Now <i class="fa-solid fa-arrow-right"></i></a>
                <button class="nav-toggle" id="navToggle" aria-label="Open menu" aria-expanded="false" aria-controls="mobileNav"><i class="fa-solid fa-bars"></i></button>
            </div></div></header>
            <div class="mobile-nav" id="mobileNav" aria-hidden="true"><div class="mn-backdrop"></div><div class="mn-panel" role="dialog" aria-label="Menu">
                <div class="mn-head">${UI.brand(r + "index.html")}<button class="modal-close" id="mnClose" aria-label="Close menu"><i class="fa-solid fa-xmark"></i></button></div>
                <ul class="mn-links">${NAV.map(([h, t, i]) => `<li><a href="${r}${h}" class="${isActive(h) ? "active" : ""}"><i class="fa-solid ${i}"></i>${t}</a></li>`).join("")}
                    <li><a href="${r}pages/login.html?role=student"><i class="fa-solid fa-user-graduate"></i>Student Portal</a></li><li><a href="${r}pages/login.html?role=staff"><i class="fa-solid fa-briefcase"></i>Staff Portal</a></li></ul>
                <a class="btn btn-primary btn-lg btn-block" href="${r}pages/application.html">Apply Now</a>
                <div class="mt-3 small muted">${TSCE_FLYER.phones.map((p) => `<div><i class="fa-solid fa-phone"></i> <a href="tel:${p.replace(/\s/g, "")}">${p}</a></div>`).join("")}</div>
            </div></div>`;
        UI.$("#site-header").outerHTML = html;

        const hdr = UI.$("#siteHeader");
        const onScroll = () => hdr.classList.toggle("scrolled", scrollY > 8);
        addEventListener("scroll", onScroll, { passive: true }); onScroll();
        const mn = UI.$("#mobileNav"), tg = UI.$("#navToggle");
        let release = null;
        const setMn = (open) => { mn.classList.toggle("open", open); mn.setAttribute("aria-hidden", !open); tg.setAttribute("aria-expanded", open); document.body.style.overflow = open ? "hidden" : ""; if (open) setTimeout(() => UI.$("#mnClose").focus(), 50); else tg.focus(); };
        tg.onclick = () => setMn(true);
        UI.$("#mnClose").onclick = () => setMn(false);
        UI.$(".mn-backdrop").onclick = () => setMn(false);
        mn.addEventListener("keydown", (e) => e.key === "Escape" && setMn(false));
        UI.$$(".mn-links a").forEach((a) => a.addEventListener("click", () => setMn(false)));
        const dd = UI.$("#portalDrop");
        dd.querySelector("button").onclick = (e) => { e.stopPropagation(); const o = !dd.classList.contains("open"); dd.classList.toggle("open", o); e.currentTarget.setAttribute("aria-expanded", o); };
        document.addEventListener("click", () => dd.classList.remove("open"));
        document.addEventListener("keydown", (e) => e.key === "Escape" && dd.classList.remove("open"));
        setInterval(() => { const c = UI.$("#abCount"); if (c) c.textContent = countdownText(); }, 60000);
    }

    function footer() {
        const r = UI.root();
        const el = UI.$("#site-footer");
        if (!el) return;
        el.outerHTML = `<footer class="site-footer"><div class="container">
            <div class="footer-grid">
                <div>${UI.brand(r + "index.html")}<p class="mt-2" style="max-width:300px">Practical, career-focused digital skills training for the next generation of technology professionals in Northern Nigeria and beyond.</p>
                    <ul class="f-contact mt-2"><li><i class="fa-solid fa-location-dot"></i><span>${TSCE_FLYER.address}</span></li></ul></div>
                <div><h5>TSCE</h5><ul><li><a href="${r}pages/about.html">About</a></li><li><a href="${r}pages/programmes.html">Programmes</a></li><li><a href="${r}pages/admissions.html">Admissions</a></li><li><a href="${r}pages/contact.html">Contact</a></li></ul></div>
                <div><h5>Students</h5><ul><li><a href="${r}pages/login.html?role=student">Student Portal</a></li><li><a href="${r}pages/student/payments.html">Payments</a></li><li><a href="${r}pages/student/results.html">Results</a></li><li><a href="${r}pages/verify.html">Certificates</a></li></ul></div>
                <div><h5>Resources</h5><ul><li><a href="${r}pages/news.html">News</a></li><li><a href="${r}pages/news.html#events">Events</a></li><li><a href="${r}index.html#faq">FAQs</a></li><li><a href="${r}pages/contact.html">Support</a></li></ul></div>
                <div><h5>Connect</h5><ul class="f-contact">${TSCE_FLYER.phones.map((p) => `<li><i class="fa-solid fa-phone"></i><a href="tel:${p.replace(/\s/g, "")}">${p}</a></li>`).join("")}<li><i class="fa-solid fa-globe"></i><a href="#">${TSCE_FLYER.website}</a></li></ul>
                    <div class="socials mt-2">${TSCE_FLYER.socials.map((s) => `<a href="${s.url}" aria-label="${s.label}" title="${s.label}"><i class="fa-brands ${s.icon}"></i></a>`).join("")}</div></div>
            </div>
            <div class="footer-bottom"><span>© 2026 ${TSCE_FLYER.name}. All rights reserved.</span><span class="motto">${TSCE_FLYER.motto.join('<span>|</span>')}</span></div>
        </div></footer>`;
    }

    return { header, footer };
})();

/* ---------------- Public: Home ---------------- */
Pages["home"] = function () {
    // Featured programmes
    const featured = ["fullstack", "cyber-fund", "data-ai", "network", "digital-marketing", "cisco-cloud"].map(Programmes.get).filter((p) => p && p.status === "Active");
    UI.$("#featuredProgs").innerHTML = featured.map(Programmes.card).join("");
    Programmes.bindCards(UI.$("#featuredProgs"));

    // Testimonials: hidden until TSCE supplies real ones (the demo quotes were invented).

    // Countdown
    const target = new Date(`${Site.cohortDate || TSCE_FLYER.startDate}T08:00:00`);
    const tick = () => {
        const ms = Math.max(0, target - Date.now());
        const v = [Math.floor(ms / 864e5), Math.floor(ms / 36e5) % 24, Math.floor(ms / 6e4) % 60, Math.floor(ms / 1e3) % 60];
        UI.$$("#countdown strong").forEach((el, i) => el.textContent = String(v[i]).padStart(2, "0"));
    };
    tick(); setInterval(tick, 1000);

    // Timeline "now" flag + early-bird state
    const eb = Discounts.earlyBirdOpen();
    UI.$("#ebFlag").innerHTML = eb ? `<span class="badge badge-success now-flag">Early bird active</span>` : `<span class="badge badge-neutral now-flag">Closed</span>`;

    // Career pathway animation — cycle the active stage
    const path = UI.$("#pathway");
    const steps = UI.$$(".path-step", path);
    let i = 0;
    const obs = new IntersectionObserver((en) => { if (en[0].isIntersecting) { path.classList.add("in"); obs.disconnect(); setInterval(() => { steps.forEach((s, k) => s.classList.toggle("active", k === i)); i = (i + 1) % steps.length; }, 1400); } }, { threshold: .3 });
    obs.observe(path);

    faq();
    UI.animateAll();
};

function faq() {
    UI.$$(".faq-item").forEach((it) => {
        const q = it.querySelector(".faq-q");
        q.addEventListener("click", () => { const o = !it.classList.contains("open"); it.classList.toggle("open", o); q.setAttribute("aria-expanded", o); });
    });
}

Pages["about"] = function () { UI.animateAll(); };
Pages["admissions"] = function () {
    const eb = Discounts.earlyBirdOpen();
    const ex = UI.$("#feeExample");
    if (ex) {
        const p = Programmes.get("fullstack"), f = Discounts.compute(p.fee, { applyEarlyBird: true });
        ex.innerHTML = `<div class="fee-box"><div class="fee-head"><strong style="font-family:var(--font-head)">Example: ${UI.esc(p.name)}</strong>${eb ? UI.badge("Early bird active") : UI.badge("Closed")}</div>
            <div class="fee-row"><span>Programme Fee</span><span>${UI.naira(f.fee)}</span></div><div class="fee-row"><span>Early Bird Discount (${f.pct}%)</span><span class="neg">−${UI.naira(f.discount)}</span></div><div class="fee-row total"><span>Amount Payable</span><span>${UI.naira(f.payable)}</span></div></div>`;
    }
    UI.$("#feeTable").innerHTML = Programmes.active().map((p) => `<tr><td><div class="person"><span class="icon-tile" style="width:34px;height:34px;border-radius:10px;background:${p.color};color:#fff;font-size:.8rem"><i class="fa-solid ${p.icon}"></i></span><strong>${UI.esc(p.name)}</strong></div></td><td>${p.weeks} Weeks</td><td class="num"><b>${UI.naira(p.fee)}</b></td><td class="num" style="color:var(--success);font-weight:700">${UI.naira(p.fee * .85)}</td><td class="num">${UI.naira(p.fee * .5)}</td><td><a class="btn btn-xs btn-soft" href="application.html?programme=${p.id}">Apply</a></td></tr>`).join("");
    faq();
    UI.animateAll();
};
Pages["contact"] = function () {
    const f = UI.$("#contactForm");
    UI.$("#c_prog").innerHTML = `<option value="">General enquiry</option>` + Programmes.active().map((p) => `<option>${UI.esc(p.name)}</option>`).join("");
    UI.liveValidate(f);
    f.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!UI.validate(f)) return;
        const btn = UI.$("button[type=submit]", f);
        btn.disabled = true; btn.innerHTML = `<span class="spinner"></span> Sending…`;
        const d = UI.formData(f);
        try {
            await API.post("enquiries", { name: d.name, email: d.email, phone: d.phone || "", programme: d.programme || "", subject: d.subject || "", message: d.message });
        } catch (err) {
            btn.disabled = false; btn.innerHTML = `Send message <i class="fa-solid fa-paper-plane"></i>`;
            if (!API.showFieldErrors(f, err)) UI.toast("Message not sent", err.message, "error");
            return;
        }
        f.reset();
        btn.disabled = false; btn.innerHTML = `Send message <i class="fa-solid fa-paper-plane"></i>`;
        UI.modal({ size: "sm", bare: true, body: `<div class="processing"><div class="success-mark"><svg viewBox="0 0 52 52"><path d="M14 27l8 8 16-17"/></svg></div><h3>Message sent</h3><p class="muted">Thank you, ${UI.esc(d.name.split(" ")[0])}. Our admissions team will reply within 24 hours.</p><button class="btn btn-primary" data-close>Close</button></div>` });
    });
    UI.animateAll();
};

/* ---------------- Router ---------------- */
document.addEventListener("DOMContentLoaded", async () => {
    const body = document.body;
    // Who is signed in + settings and programmes, cached for synchronous use.
    await Promise.all([Auth.load(), Site.load()]);
    const page = body.dataset.page;
    UI.$$("[data-brand]").forEach((el) => el.outerHTML = UI.brand(UI.url("index.html")));
    const portal = body.dataset.portal;

    if (portal) {
        const session = Auth.require(portal);
        if (!session) return;
        body.classList.add("portal");
        let ctx = { session };
        if (portal === "student") {
            const student = DB.get("students", session.studentId) || DB.first("students", (s) => s.email === session.email);
            if (!student) {
                // TRANSITION (until Phase 7): student pages still read demo data from localStorage.
                Dashboard.mount(portal, page, session);
                UI.$("#view").innerHTML = UI.empty({ icon: "fa-person-digging", title: "Your student portal is almost ready", text: "We're connecting your programme, attendance and results. Your account and payment are safe — check back soon." });
                if (session.mustChangePassword) Auth.forcePasswordChange();
                return;
            }
            ctx.student = student;
        }
        if (portal === "staff" && ["staff-settings", "staff-staff"].includes(page) && session.role !== "admin") {
            UI.$("#view").innerHTML = UI.empty({ icon: "fa-lock", title: "Admin access required", text: "Only administrators can manage staff and platform settings.", action: `<a class="btn btn-primary" href="dashboard.html">Back to dashboard</a>` });
            Dashboard.mount(portal, page, session);
            return;
        }
        Dashboard.mount(portal, page, session);
        if (session.mustChangePassword) Auth.forcePasswordChange();
        const view = UI.$("#view");
        if (Dashboard.isSoon(portal, page)) {
            view.innerHTML = UI.empty({ icon: "fa-person-digging", title: "Coming soon", text: "This section is being connected to the live system. Its old demo data has been switched off so nobody works on fake records.", action: `<a class="btn btn-primary" href="dashboard.html">Back to dashboard</a>` });
            return;
        }
        const run = Pages[page];
        if (run) UI.safe(() => run(view, ctx), page);
        if (location.hash) setTimeout(() => UI.$(location.hash)?.scrollIntoView({ behavior: "smooth" }), 300);
        return;
    }

    if (UI.$("#site-header")) App.header(page);
    App.footer();
    if (!Site.ready) UI.toast("Connection problem", "We couldn't load the latest programme information. Check your connection and reload.", "warning", 8000);
    const run = Pages[page];
    if (run) UI.safe(run, page);
});
