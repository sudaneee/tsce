/* ==========================================================================
   TSCE — Portal shell (sidebar, topbar, global search, notifications)
   and the Student / Staff dashboards, Staff directory, Settings.
   ========================================================================== */

const Dashboard = (() => {
    const NAV = {
        student: [
            { label: "Main" },
            { id: "student-dashboard", href: "dashboard.html", icon: "fa-gauge-high", text: "Dashboard" },
            { id: "student-profile", href: "profile.html", icon: "fa-user", text: "My Profile" },
            { id: "student-programme", href: "programme.html", icon: "fa-layer-group", text: "My Programme" },
            { id: "student-learning", href: "learning.html", icon: "fa-book-open-reader", text: "Learning" },
            { label: "Academics" },
            { id: "student-attendance", href: "attendance.html", icon: "fa-calendar-check", text: "Attendance" },
            { id: "student-assessments", href: "results.html#assessments", icon: "fa-pen-ruler", text: "Assessments" },
            { id: "student-results", href: "results.html", icon: "fa-chart-simple", text: "Results" },
            { id: "student-certificates", href: "certificates.html", icon: "fa-certificate", text: "Certificates" },
            { label: "Account" },
            { id: "student-payments", href: "payments.html", icon: "fa-wallet", text: "Payments" },
            { id: "student-announcements", href: "announcements.html", icon: "fa-bullhorn", text: "Announcements", count: () => Notifications.unread() },
            { id: "student-support", href: "support.html", icon: "fa-headset", text: "Support" },
            { id: "student-settings", href: "settings.html", icon: "fa-gear", text: "Settings" }
        ],
        staff: [
            { label: "Overview" },
            { id: "staff-dashboard", href: "dashboard.html", icon: "fa-gauge-high", text: "Dashboard" },
            { label: "Admissions" },
            { id: "staff-applications", href: "applications.html", icon: "fa-file-signature", text: "Applications" },
            { id: "staff-scholarships", href: "scholarships.html", icon: "fa-award", text: "Excellence Awards", count: () => 0 },
            { id: "staff-payments", href: "payments.html", icon: "fa-naira-sign", text: "Payments", count: () => 0 },
            { label: "Academics" },
            // soon: not yet on the live API — shown disabled so nobody works on demo data.
            { id: "staff-students", href: "students.html", icon: "fa-user-graduate", text: "Students", soon: true },
            { id: "staff-programmes", href: "programmes.html", icon: "fa-layer-group", text: "Programmes", soon: true },
            { id: "staff-attendance", href: "attendance.html", icon: "fa-calendar-check", text: "Attendance", soon: true },
            { id: "staff-assessments", href: "assessments.html", icon: "fa-pen-ruler", text: "Assessments", soon: true },
            { id: "staff-certificates", href: "certificates.html", icon: "fa-certificate", text: "Certificates", soon: true },
            { label: "Management" },
            { id: "staff-staff", href: "staff.html", icon: "fa-id-badge", text: "Staff", admin: true },
            { id: "staff-announcements", href: "announcements.html", icon: "fa-bullhorn", text: "Announcements", soon: true },
            { id: "staff-reports", href: "reports.html", icon: "fa-chart-pie", text: "Reports", soon: true },
            { id: "staff-settings", href: "settings.html", icon: "fa-gear", text: "Settings", admin: true }
        ]
    };
    const TITLES = {
        "student-dashboard": ["Dashboard", "Your learning at a glance"], "student-profile": ["My Profile", "Personal information"], "student-programme": ["My Programme", "Modules & progress"], "student-learning": ["Learning", "Lessons & resources"], "student-attendance": ["Attendance", "Class attendance"], "student-results": ["Results", "Assessments & grades"], "student-payments": ["Payments", "Invoices & receipts"], "student-certificates": ["Certificates", "Completion & verification"], "student-announcements": ["Announcements", "News & notifications"], "student-support": ["Support", "Help desk"], "student-settings": ["Settings", "Account preferences"],
        "staff-dashboard": ["Dashboard", "Institution overview"], "staff-applications": ["Applications", "Admissions pipeline"], "staff-students": ["Students", "Learner records"], "staff-programmes": ["Programmes", "Catalogue management"], "staff-payments": ["Payments", "Zainpay transactions"], "staff-attendance": ["Attendance", "Class registers"], "staff-assessments": ["Assessments", "Gradebook"], "staff-scholarships": ["Excellence Awards", "Verify results in person"], "staff-certificates": ["Certificates", "Issue & verify"], "staff-reports": ["Reports", "Analytics & exports"], "staff-announcements": ["Announcements", "Communications"], "staff-settings": ["Settings", "Platform configuration"], "staff-staff": ["Staff", "Team directory"]
    };

    /* ---------- Charts ---------- */
    const charts = {};
    function chart(id, cfg) {
        const el = document.getElementById(id);
        if (!el || !window.Chart) return null;
        if (charts[id]) charts[id].destroy();
        Chart.defaults.font.family = "Inter, system-ui, sans-serif";
        Chart.defaults.font.size = 12;
        Chart.defaults.color = "#64708D";
        Chart.defaults.borderColor = "#EDF1F8";
        Chart.defaults.plugins.tooltip.backgroundColor = "#0B1D55";
        Chart.defaults.plugins.tooltip.padding = 10;
        Chart.defaults.plugins.tooltip.cornerRadius = 10;
        Chart.defaults.plugins.legend.labels.usePointStyle = true;
        Chart.defaults.plugins.legend.labels.boxWidth = 8;
        cfg.options = { responsive: true, maintainAspectRatio: false, ...(cfg.options || {}) };
        const isCircular = ["doughnut", "pie"].includes(cfg.type);
        if (!isCircular) {
            cfg.options.scales = cfg.options.scales || {};
            ["x", "y"].forEach((ax) => { cfg.options.scales[ax] = { grid: { display: ax === (cfg.options.indexAxis === "y" ? "x" : "y"), drawBorder: false }, border: { display: false }, ...(cfg.options.scales[ax] || {}) }; });
        }
        charts[id] = new Chart(el, cfg);
        return charts[id];
    }
    /** Deterministic pseudo-noise for demo-only chart filler (same value every load). */
    function seedNoise(key) { let h = 0; for (const c of String(key)) h = (h * 31 + c.charCodeAt(0)) | 0; return Math.abs(h) % 3; }

    /* ---------- Shell ---------- */
    function sidebarHTML(portal, page, s) {
        const items = NAV[portal].filter((i) => !i.admin || s.role === "admin");
        const nav = items.map((i) => i.label ? `<div class="sb-label">${i.label}</div>` :
            i.soon ? `<span class="sb-link" style="opacity:.45;cursor:default" data-tip="${i.text} (coming soon)" aria-disabled="true"><i class="fa-solid ${i.icon}"></i><span>${i.text}</span><b class="sb-count" style="background:transparent;color:inherit;font-weight:600">soon</b></span>` :
            `<a class="sb-link ${i.id === page ? "active" : ""}" href="${i.href}" data-tip="${i.text}" ${i.id === page ? 'aria-current="page"' : ""}><i class="fa-solid ${i.icon}"></i><span>${i.text}</span>${i.count ? `<b class="sb-count" data-count-for="${i.id}" hidden></b>` : ""}</a>`).join("");
        return `<div class="sb-head">${UI.brand("../../index.html")}<button class="sb-collapse" id="sbCollapse" aria-label="Collapse sidebar"><i class="fa-solid fa-angles-left"></i></button></div>
            <div class="sb-portal"><span class="dot"></span><div class="txt"><b>${portal === "student" ? "Student Portal" : s.role === "admin" ? "Admin Console" : "Staff Portal"}</b>${portal === "student" ? UI.esc(s.studentId || "") : "TSCE · Zaria"}</div></div>
            <nav class="sb-nav" aria-label="Portal navigation">${nav}</nav>
            <div class="sb-foot"><div class="sb-user">${UI.avatar(s.name, "sm")}<div class="meta"><strong>${UI.esc(s.name)}</strong><span>${s.role}</span></div><button id="sbLogout" aria-label="Log out" title="Log out"><i class="fa-solid fa-arrow-right-from-bracket"></i></button></div></div>`;
    }
    function topbarHTML(portal, page, s) {
        const [t, sub] = TITLES[page] || ["", ""];
        return `<button class="tb-btn tb-menu" id="tbMenu" aria-label="Open menu"><i class="fa-solid fa-bars"></i></button>
            <div class="tb-title"><h1>${t}</h1><p>${sub}</p></div>
            ${portal === "staff" ? `<div class="tb-search" id="tbSearch"><i class="fa-solid fa-magnifying-glass"></i><input class="input" id="gSearch" type="search" placeholder="Search students, applications, payments…" aria-label="Global search" autocomplete="off"><kbd>Ctrl K</kbd><div class="search-results" id="gResults" role="listbox"></div></div>` : `<span style="margin-left:auto"></span>`}
            <div class="tb-actions">
                ${portal === "staff" ? `<button class="tb-btn" id="mSearchBtn" aria-label="Search" style="display:none"><i class="fa-solid fa-magnifying-glass"></i></button>` : ""}
                <div class="dropdown" id="bellDD"><button class="tb-btn" id="bellBtn" aria-label="Notifications" aria-haspopup="true"><i class="fa-regular fa-bell"></i><span class="dotcount" id="bellCount" hidden></span></button>
                    <div class="dropdown-menu" role="menu"><div class="dm-head"><h4>Notifications</h4><button class="link-btn small" id="bellReadAll">Mark all read</button></div><div class="dm-list" id="bellList"></div><div class="dm-foot"><a class="small" href="${portal === "student" ? "announcements.html" : "announcements.html"}">View all</a></div></div></div>
                <div class="dropdown" id="userDD"><button class="tb-user" id="userBtn" aria-haspopup="true" aria-label="Account menu">${UI.avatar(s.name, "sm")}<span class="meta-txt"><strong>${UI.esc(s.name.split(" ").slice(0, 2).join(" "))}</strong><small>${s.role}</small></span><i class="fa-solid fa-chevron-down small muted meta-txt"></i></button>
                    <div class="dropdown-menu" style="width:240px" role="menu"><div class="menu-list">
                        ${portal === "student" ? `<a href="profile.html"><i class="fa-regular fa-user"></i>My profile</a><a href="settings.html"><i class="fa-solid fa-gear"></i>Settings</a>` : `<a href="dashboard.html"><i class="fa-solid fa-gauge-high"></i>Dashboard</a>${s.role === "admin" ? `<a href="settings.html"><i class="fa-solid fa-gear"></i>Settings</a>` : ""}`}
                        <a href="../../index.html" target="_blank" rel="noopener"><i class="fa-solid fa-globe"></i>View public website</a>
                        <button id="umPassword"><i class="fa-solid fa-key"></i>Change password</button>
                        <button id="umLogout"><i class="fa-solid fa-arrow-right-from-bracket"></i>Log out</button></div></div></div>
            </div>`;
    }
    function bottomNavHTML(portal, page) {
        const items = portal === "student"
            ? [["student-dashboard", "dashboard.html", "fa-house", "Home"], ["student-programme", "programme.html", "fa-layer-group", "Programme"], ["student-results", "results.html", "fa-chart-simple", "Results"], ["student-payments", "payments.html", "fa-wallet", "Payments"]]
            : [["staff-dashboard", "dashboard.html", "fa-house", "Home"], ["staff-applications", "applications.html", "fa-file-signature", "Apps"], ["staff-students", "students.html", "fa-user-graduate", "Students"], ["staff-payments", "payments.html", "fa-naira-sign", "Payments"]];
        return items.map(([id, h, i, t]) => `<a href="${h}" class="${id === page ? "active" : ""}"><i class="fa-solid ${i}"></i>${t}</a>`).join("") + `<button id="bnMore"><i class="fa-solid fa-grip"></i>More</button>`;
    }

    let bellItems = [];
    async function refreshBell() {
        const c = UI.$("#bellCount");
        if (!c) return;
        let list = [], n = 0;
        try { const r = await API.get("notifications"); list = r.results; n = r.unread; } catch (e) { /* offline: leave the bell as is */ return; }
        bellItems = list;
        c.hidden = !n; c.textContent = n > 9 ? "9+" : n;
        UI.$("#bellList").innerHTML = list.length ? list.slice(0, 8).map(Notifications.itemHTML).join("") : UI.empty({ icon: "fa-bell-slash", title: "No notifications" });
        UI.$$("#bellList [data-nid]").forEach((el) => {
            const open = async () => {
                const item = bellItems.find((x) => String(x.id) === el.dataset.nid);
                try { await API.post(`notifications/${el.dataset.nid}/read`); } catch (e) { /* ignore */ }
                if (item?.link) location.href = UI.url(item.link); else refreshBell();
            };
            el.onclick = open; el.onkeydown = (e) => e.key === "Enter" && open();
        });
        refreshSidebarCounts();
    }
    function refreshSidebarCounts() {
        if (document.body.dataset.portal === "staff" && typeof Staff !== "undefined") Staff.refreshCounts();
    }
    const isSoon = (portal, page) => !!NAV[portal]?.find((i) => i.id === page && i.soon);

    /* ---------- Global search (staff) ---------- */
    function initSearch() {
        const input = UI.$("#gSearch"), box = UI.$("#gResults");
        if (!input) return;
        let hl = -1;
        const mark = (t, q) => UI.esc(t).replace(new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "ig"), "<mark>$1</mark>");
        let seq = 0;
        async function search() {
            const q = input.value.trim();
            if (q.length < 2) { box.classList.remove("open"); return; }
            const mine = ++seq;
            let r;
            try { r = await API.get("staff/search", { q }); } catch (e) { return; }
            if (mine !== seq) return;  // a newer search has started
            const groups = [
                ["Applications", r.applications.map((a) => ({ href: `applications.html?id=${encodeURIComponent(a.id)}`, icon: "fa-file-signature", tone: "cyan", title: a.name, sub: `${a.id} · ${a.programme} · ${a.status}` }))],
                ["Students", r.students.map((s) => ({ href: `applications.html`, icon: "fa-user-graduate", tone: "", title: s.name, sub: s.id }))],
                ["Payments", r.payments.map((p) => ({ href: `payments.html?ref=${encodeURIComponent(p.ref)}`, icon: "fa-naira-sign", tone: "green", title: p.ref, sub: `${p.name} · ${UI.naira(p.amount)} · ${p.status}` }))]
            ].filter(([, rows]) => rows.length);

            hl = -1;
            box.innerHTML = groups.length ? groups.map(([g, rows]) => `<div class="sr-group">${g}</div>` + rows.map((r) => `<a class="sr-item" href="${r.href}" role="option"><span class="icon-tile ${r.tone}"><i class="fa-solid ${r.icon}"></i></span><div><strong>${mark(r.title, q)}</strong><small>${mark(r.sub, q)}</small></div></a>`).join("")).join("")
                : `<div class="sr-empty"><i class="fa-solid fa-magnifying-glass"></i><br>No results for “${UI.esc(q)}”</div>`;
            box.classList.add("open");
        }
        input.addEventListener("input", UI.debounce(search, 120));
        input.addEventListener("focus", search);
        input.addEventListener("keydown", (e) => {
            const items = UI.$$(".sr-item", box);
            if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); hl = (hl + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length; items.forEach((x, i) => x.classList.toggle("hl", i === hl)); items[hl]?.scrollIntoView({ block: "nearest" }); }
            if (e.key === "Enter" && items[Math.max(0, hl)]) { location.href = items[Math.max(0, hl)].href; }
            if (e.key === "Escape") { box.classList.remove("open"); input.blur(); UI.$("#tbSearch").classList.remove("m-open"); }
        });
        document.addEventListener("click", (e) => { if (!e.target.closest("#tbSearch") && !e.target.closest("#mSearchBtn")) { box.classList.remove("open"); UI.$("#tbSearch").classList.remove("m-open"); } });
        document.addEventListener("keydown", (e) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); UI.$("#tbSearch").classList.add("m-open"); input.focus(); } });
        const mBtn = UI.$("#mSearchBtn");
        const mq = window.matchMedia("(max-width: 820px)");
        const sync = () => mBtn.style.display = mq.matches ? "grid" : "none";
        mq.addEventListener ? mq.addEventListener("change", sync) : mq.addListener(sync); sync();
        mBtn.onclick = () => { UI.$("#tbSearch").classList.add("m-open"); input.focus(); };
    }

    function changePasswordModal() {
        const m = UI.modal({
            title: "Change password", size: "sm",
            body: `<form id="cpForm" class="form-grid" novalidate style="grid-template-columns:1fr">
                <div class="field"><label for="cp0">Current password <span class="req">*</span></label><input id="cp0" name="currentPassword" type="password" class="input" required autocomplete="current-password"></div>
                <div class="field"><label for="cp1">New password <span class="req">*</span></label><input id="cp1" name="newPassword" type="password" class="input" required minlength="8" autocomplete="new-password"></div>
                <div class="field"><label for="cp2">Confirm new password <span class="req">*</span></label><input id="cp2" type="password" class="input" required data-match="cp1" autocomplete="new-password"></div></form>`,
            footer: `<button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-primary" id="cpSave">Update password</button>`
        });
        const f = UI.$("#cpForm", m.el);
        UI.liveValidate(f);
        UI.$("#cpSave", m.el).onclick = async () => {
            if (!UI.validate(f)) return;
            try {
                await Auth.changePassword(UI.$("#cp0", m.el).value, UI.$("#cp1", m.el).value);
                m.close(); UI.toast("Password updated", "Use your new password next time you sign in.", "success");
            } catch (err) { if (!API.showFieldErrors(f, err)) UI.toast("Couldn't update password", err.message, "error"); }
        };
    }

    function mount(portal, page, s) {
        const shell = UI.$(".app-shell");
        UI.$("#sidebar").innerHTML = sidebarHTML(portal, page, s);
        UI.$("#topbar").innerHTML = topbarHTML(portal, page, s);
        const bn = document.createElement("nav"); bn.className = "bottom-nav"; bn.setAttribute("aria-label", "Quick navigation"); bn.innerHTML = bottomNavHTML(portal, page); document.body.appendChild(bn);
        try { if (localStorage.getItem("tsce_ui_sb") === "1") shell.classList.add("collapsed"); } catch (e) { /* ignore */ }
        UI.$("#sbCollapse").onclick = () => { shell.classList.toggle("collapsed"); try { localStorage.setItem("tsce_ui_sb", shell.classList.contains("collapsed") ? "1" : "0"); } catch (e) { /* ignore */ } };
        const openSb = () => shell.classList.add("sb-open");
        UI.$("#tbMenu").onclick = openSb; UI.$("#bnMore").onclick = openSb;
        shell.addEventListener("click", (e) => { if (shell.classList.contains("sb-open") && !e.target.closest(".sidebar") && !e.target.closest("#tbMenu")) shell.classList.remove("sb-open"); });
        const logout = async () => { if (await UI.confirm({ title: "Log out?", message: "You'll need to sign in again to access the portal.", confirmText: "Log out", icon: "fa-arrow-right-from-bracket" })) Auth.logout(); };
        UI.$("#sbLogout").onclick = logout; UI.$("#umLogout").onclick = logout;
        UI.$("#umPassword").onclick = () => changePasswordModal();
        // Dropdowns
        UI.$$(".dropdown").forEach((dd) => {
            const btn = dd.querySelector("button");
            btn.addEventListener("click", (e) => { e.stopPropagation(); const open = !dd.classList.contains("open"); UI.$$(".dropdown.open").forEach((x) => x.classList.remove("open")); dd.classList.toggle("open", open); btn.setAttribute("aria-expanded", open); });
        });
        document.addEventListener("click", (e) => { if (!e.target.closest(".dropdown")) UI.$$(".dropdown.open").forEach((x) => x.classList.remove("open")); });
        document.addEventListener("keydown", (e) => { if (e.key === "Escape") UI.$$(".dropdown.open").forEach((x) => x.classList.remove("open")); });
        UI.$("#bellReadAll").onclick = async (e) => { e.stopPropagation(); try { await API.post("notifications/read-all"); } catch (err) { /* ignore */ } refreshBell(); };
        refreshBell();
        initSearch();
    }

    return { NAV, chart, seedNoise, mount, refreshBell, refreshSidebarCounts, isSoon };
})();

/* ---------------- Student dashboard ---------------- */
Pages["student-dashboard"] = function (view, { student: s }) {
    const p = Programmes.get(s.programmeId);
    const att = Students.attendance(s.id), res = Students.results(s.id);
    const mods = Students.modules(s);
    const cur = mods.find((m) => m.pct < 100);
    const app = DB.get("applications", s.appId);
    const paid = s.paymentStatus === "Paid";
    const started = new Date(s.startDate) <= new Date();
    const hr = new Date().getHours();
    const greet = hr < 12 ? "Good morning" : hr < 17 ? "Good afternoon" : "Good evening";
    const next = (() => { const d = new Date(Math.max(Date.now(), new Date(s.startDate))); while (![1, 3, 5].includes(d.getDay()) || d < new Date(s.startDate)) d.setDate(d.getDate() + 1); return d; })();
    const anns = Announcements.visibleTo("Students").slice(0, 3);
    const diff = Math.max(0, new Date(s.startDate) - Date.now());

    view.innerHTML = `${pendingBanner(s)}
        <div class="welcome">
            <div style="position:relative;z-index:1"><span class="badge badge-primary no-dot">${UI.esc(s.cohort)} · ${UI.esc(s.id)}</span>
                <h2>${greet}, ${UI.esc(s.firstName)} 👋</h2>
                <p>${s.status === "Completed" ? `Congratulations on completing <b>${UI.esc(p.name)}</b>! Your certificate is available.` : started ? `You're making great progress in <b>${UI.esc(p.name)}</b>. Next class: <b>${UI.date(next, { weekday: "long", day: "numeric", month: "short" })}</b>${cur ? ` — ${UI.esc(cur.name)}` : ""}.` : `Welcome to TSCE! <b>${UI.esc(p.name)}</b> begins on <b>${UI.dateLong(s.startDate)}</b>.`}</p></div>
            <div class="actions">${s.status === "Completed" ? `<a class="btn btn-primary" href="certificates.html"><i class="fa-solid fa-certificate"></i> View certificate</a>` : `<a class="btn btn-primary" href="learning.html"><i class="fa-solid fa-play"></i> Continue learning</a>`}<a class="btn btn-outline" href="results.html"><i class="fa-solid fa-chart-simple"></i> Results</a></div>
        </div>
        <div class="kpis">
            <div class="kpi"><div class="kpi-top"><p class="label">Programme Progress</p><span class="icon-tile"><i class="fa-solid fa-bars-progress"></i></span></div><div class="value" data-count="${s.progress}" data-suffix="%">0%</div><div class="progress kpi-progress"><span data-value="${s.progress}"></span></div></div>
            <div class="kpi"><div class="kpi-top"><p class="label">Attendance</p><span class="icon-tile green"><i class="fa-solid fa-calendar-check"></i></span></div><div class="value" ${att.total ? `data-count="${att.rate}" data-suffix="%"` : ""}>${att.total ? "0%" : "—"}</div>${att.total ? `<div class="progress kpi-progress green"><span data-value="${att.rate}"></span></div>` : `<div class="small muted mt-1">Starts with first class</div>`}</div>
            <div class="kpi"><div class="kpi-top"><p class="label">Assessment Average</p><span class="icon-tile cyan"><i class="fa-solid fa-chart-line"></i></span></div><div class="value" ${res.recs.length ? `data-count="${res.avg}" data-suffix="%"` : ""}>${res.recs.length ? "0%" : "—"}</div>${res.recs.length ? `<span class="trend up"><i class="fa-solid fa-arrow-trend-up"></i> Grade ${res.grade}</span>` : `<div class="small muted mt-1">No results yet</div>`}</div>
            <div class="kpi"><div class="kpi-top"><p class="label">Payment Status</p><span class="icon-tile ${paid ? "green" : "red"}"><i class="fa-solid fa-wallet"></i></span></div><div class="value">${paid ? "Paid" : "Unpaid"}</div><div class="small muted mt-1">${paid ? `${UI.naira(app?.amountPayable || s.amountPaid)} · Zainpay` : "Outstanding balance"}</div></div>
        </div>
        <div class="dash-grid cols-12">
            ${started ? `<div class="panel span-8"><div class="panel-head"><div><h3><i class="fa-solid fa-list-check"></i>Module progress</h3><p>${mods.filter((m) => m.pct >= 100).length} of ${mods.length} completed</p></div><a class="btn btn-sm btn-ghost" href="programme.html">View all <i class="fa-solid fa-arrow-right"></i></a></div>
                ${mods.slice(Math.max(0, (cur ? cur.index : mods.length) - 3), Math.max(0, (cur ? cur.index : mods.length) - 3) + 5).map((m) => `<div class="module ${m.pct >= 100 ? "done" : m === cur ? "current" : ""}"><div class="m-ic">${m.pct >= 100 ? '<i class="fa-solid fa-check"></i>' : String(m.index + 1).padStart(2, "0")}</div><div><h4>${UI.esc(m.name)}</h4><div class="progress sm ${m.pct >= 100 ? "green" : ""}"><span data-value="${m.pct}"></span></div></div><div class="m-status" style="color:${m.pct >= 100 ? "var(--success)" : m.pct ? "var(--primary)" : "var(--muted-2)"}">${m.pct >= 100 ? "✓ Completed" : m.pct ? m.pct + "%" : "Not started"}</div></div>`).join("")}
            </div>` : `<div class="panel span-8"><div class="panel-head"><h3><i class="fa-solid fa-rocket"></i>Your programme starts soon</h3></div><div class="panel-body">
                <div class="countdown-grid">${[["Days", Math.floor(diff / 864e5)], ["Hours", Math.floor(diff / 36e5) % 24], ["Minutes", Math.floor(diff / 6e4) % 60], ["Modules", p.modules.length]].map(([l, v]) => `<div><strong>${v}</strong><span>${l}</span></div>`).join("")}</div>
                <ul class="checklist"><li>Payment confirmed — receipt available under Payments</li><li>Attend orientation before ${UI.date(s.startDate)}</li><li>Bring a valid ID and your admission slip</li><li>Laptop recommended for practical sessions</li></ul></div></div>`}
            <div class="panel span-4"><div class="panel-head"><h3><i class="fa-regular fa-calendar"></i>Upcoming</h3></div>
                ${[0, 1, 2].map((i) => { const d = new Date(next); let k = 0; while (k < i) { d.setDate(d.getDate() + 1); if ([1, 3, 5].includes(d.getDay())) k++; } return `<div class="sched"><div class="d"><b>${d.getDate()}</b><small>${d.toLocaleDateString("en-GB", { month: "short" })}</small></div><div class="grow"><strong style="font-size:.9rem">${UI.esc((cur || mods[0]).name)}</strong><div class="small muted">${UI.esc(s.schedule.split(" (")[0])} · Lab 2</div></div></div>`; }).join("")}
                <div class="sched"><div class="d" style="background:var(--gold-50)"><b style="color:#A77A00">${new Date(s.endDate).getDate()}</b><small style="color:#A77A00">${new Date(s.endDate).toLocaleDateString("en-GB", { month: "short" })}</small></div><div class="grow"><strong style="font-size:.9rem">Programme completion</strong><div class="small muted">Capstone & certification</div></div></div>
            </div>
            <div class="panel span-7"><div class="panel-head"><div><h3><i class="fa-solid fa-chart-column"></i>Recent results</h3><p>Scores by module</p></div><a class="btn btn-sm btn-ghost" href="results.html">All results <i class="fa-solid fa-arrow-right"></i></a></div><div class="panel-body">${res.recs.length ? `<div class="chart-box sm"><canvas id="sdRes"></canvas></div>` : UI.empty({ icon: "fa-chart-simple", title: "No results yet", text: "Results appear once your instructors publish them." })}</div></div>
            <div class="panel span-5"><div class="panel-head"><h3><i class="fa-solid fa-bullhorn"></i>Announcements</h3><a class="btn btn-sm btn-ghost" href="announcements.html">View all</a></div>${anns.map((a) => `<div class="list-item"><span class="icon-tile ${a.pinned ? "gold" : ""}"><i class="fa-solid ${Announcements.iconFor(a.tag).replace("fa-calendar-star", "fa-calendar-days")}"></i></span><div class="grow"><strong>${UI.esc(a.title)}</strong><small>${UI.date(a.createdAt)} · ${UI.esc(a.author)}</small></div></div>`).join("")}</div>
            <div class="span-12"><div class="quick">${[["programme.html", "fa-layer-group", "", "My Programme"], ["attendance.html", "fa-calendar-check", "green", "Attendance"], ["payments.html", "fa-receipt", "gold", "Receipts"], ["certificates.html", "fa-certificate", "cyan", "Certificate"]].map(([h, i, c, t]) => `<a href="${h}"><span class="icon-tile ${c}"><i class="fa-solid ${i}"></i></span>${t}</a>`).join("")}</div></div>
        </div>`;
    UI.animateAll(view);
    if (res.recs.length) Dashboard.chart("sdRes", { type: "bar", data: { labels: res.recs.slice(-6).map((r) => r.module.length > 14 ? r.module.slice(0, 13) + "…" : r.module), datasets: [{ data: res.recs.slice(-6).map((r) => r.score), backgroundColor: "#1846D6", borderRadius: 8, maxBarThickness: 30 }] }, options: { plugins: { legend: { display: false } }, scales: { y: { min: 0, max: 100 } } } });
};

/* Staff dashboard, staff directory and settings: see js/staff.js (API-backed, Phase 5). */
