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
            { id: "staff-applications", href: "applications.html", icon: "fa-file-signature", text: "Applications", count: () => DB.where("applications", (a) => ["Pending", "Under Review", "Paid"].includes(a.status)).length },
            { id: "staff-scholarships", href: "scholarships.html", icon: "fa-award", text: "Scholarships", count: () => DB.where("scholarships", (s) => s.status === "Pending").length },
            { id: "staff-payments", href: "payments.html", icon: "fa-naira-sign", text: "Payments" },
            { label: "Academics" },
            { id: "staff-students", href: "students.html", icon: "fa-user-graduate", text: "Students" },
            { id: "staff-programmes", href: "programmes.html", icon: "fa-layer-group", text: "Programmes" },
            { id: "staff-attendance", href: "attendance.html", icon: "fa-calendar-check", text: "Attendance" },
            { id: "staff-assessments", href: "assessments.html", icon: "fa-pen-ruler", text: "Assessments" },
            { id: "staff-certificates", href: "certificates.html", icon: "fa-certificate", text: "Certificates" },
            { label: "Management" },
            { id: "staff-staff", href: "staff.html", icon: "fa-id-badge", text: "Staff", admin: true },
            { id: "staff-announcements", href: "announcements.html", icon: "fa-bullhorn", text: "Announcements" },
            { id: "staff-reports", href: "reports.html", icon: "fa-chart-pie", text: "Reports" },
            { id: "staff-settings", href: "settings.html", icon: "fa-gear", text: "Settings", admin: true }
        ]
    };
    const TITLES = {
        "student-dashboard": ["Dashboard", "Your learning at a glance"], "student-profile": ["My Profile", "Personal information"], "student-programme": ["My Programme", "Modules & progress"], "student-learning": ["Learning", "Lessons & resources"], "student-attendance": ["Attendance", "Class attendance"], "student-results": ["Results", "Assessments & grades"], "student-payments": ["Payments", "Invoices & receipts"], "student-certificates": ["Certificates", "Completion & verification"], "student-announcements": ["Announcements", "News & notifications"], "student-support": ["Support", "Help desk"], "student-settings": ["Settings", "Account preferences"],
        "staff-dashboard": ["Dashboard", "Institution overview"], "staff-applications": ["Applications", "Admissions pipeline"], "staff-students": ["Students", "Learner records"], "staff-programmes": ["Programmes", "Catalogue management"], "staff-payments": ["Payments", "Zainpay transactions"], "staff-attendance": ["Attendance", "Class registers"], "staff-assessments": ["Assessments", "Gradebook"], "staff-scholarships": ["Scholarships", "Awards & discounts"], "staff-certificates": ["Certificates", "Issue & verify"], "staff-reports": ["Reports", "Analytics & exports"], "staff-announcements": ["Announcements", "Communications"], "staff-settings": ["Settings", "Platform configuration"], "staff-staff": ["Staff", "Team directory"]
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
            `<a class="sb-link ${i.id === page ? "active" : ""}" href="${i.href}" data-tip="${i.text}" ${i.id === page ? 'aria-current="page"' : ""}><i class="fa-solid ${i.icon}"></i><span>${i.text}</span>${i.count ? `<b class="sb-count" data-count-for="${i.id}"></b>` : ""}</a>`).join("");
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
                <span class="demo-pill" title="All data is simulated">Demo mode</span>
                ${portal === "staff" ? `<button class="tb-btn" id="mSearchBtn" aria-label="Search" style="display:none"><i class="fa-solid fa-magnifying-glass"></i></button>` : ""}
                <div class="dropdown" id="bellDD"><button class="tb-btn" id="bellBtn" aria-label="Notifications" aria-haspopup="true"><i class="fa-regular fa-bell"></i><span class="dotcount" id="bellCount" hidden></span></button>
                    <div class="dropdown-menu" role="menu"><div class="dm-head"><h4>Notifications</h4><button class="link-btn small" id="bellReadAll">Mark all read</button></div><div class="dm-list" id="bellList"></div><div class="dm-foot"><a class="small" href="${portal === "student" ? "announcements.html" : "announcements.html"}">View all</a></div></div></div>
                <div class="dropdown" id="userDD"><button class="tb-user" id="userBtn" aria-haspopup="true" aria-label="Account menu">${UI.avatar(s.name, "sm")}<span class="meta-txt"><strong>${UI.esc(s.name.split(" ").slice(0, 2).join(" "))}</strong><small>${s.role}</small></span><i class="fa-solid fa-chevron-down small muted meta-txt"></i></button>
                    <div class="dropdown-menu" style="width:240px" role="menu"><div class="menu-list">
                        ${portal === "student" ? `<a href="profile.html"><i class="fa-regular fa-user"></i>My profile</a><a href="settings.html"><i class="fa-solid fa-gear"></i>Settings</a>` : `<a href="dashboard.html"><i class="fa-solid fa-gauge-high"></i>Dashboard</a>${s.role === "admin" ? `<a href="settings.html"><i class="fa-solid fa-gear"></i>Settings</a>` : ""}`}
                        <a href="../../index.html" target="_blank" rel="noopener"><i class="fa-solid fa-globe"></i>View public website</a>
                        <button id="umTour"><i class="fa-solid fa-compass"></i>Explore platform</button>
                        <button id="umLogout"><i class="fa-solid fa-arrow-right-from-bracket"></i>Log out</button></div></div></div>
            </div>`;
    }
    function bottomNavHTML(portal, page) {
        const items = portal === "student"
            ? [["student-dashboard", "dashboard.html", "fa-house", "Home"], ["student-programme", "programme.html", "fa-layer-group", "Programme"], ["student-results", "results.html", "fa-chart-simple", "Results"], ["student-payments", "payments.html", "fa-wallet", "Payments"]]
            : [["staff-dashboard", "dashboard.html", "fa-house", "Home"], ["staff-applications", "applications.html", "fa-file-signature", "Apps"], ["staff-students", "students.html", "fa-user-graduate", "Students"], ["staff-payments", "payments.html", "fa-naira-sign", "Payments"]];
        return items.map(([id, h, i, t]) => `<a href="${h}" class="${id === page ? "active" : ""}"><i class="fa-solid ${i}"></i>${t}</a>`).join("") + `<button id="bnMore"><i class="fa-solid fa-grip"></i>More</button>`;
    }

    function refreshBell() {
        const list = Notifications.list(), n = list.filter((x) => !x.read).length;
        const c = UI.$("#bellCount");
        if (!c) return;
        c.hidden = !n; c.textContent = n > 9 ? "9+" : n;
        UI.$("#bellList").innerHTML = list.length ? list.slice(0, 8).map(Notifications.itemHTML).join("") : UI.empty({ icon: "fa-bell-slash", title: "No notifications" });
        UI.$$("#bellList [data-nid]").forEach((el) => {
            const open = () => { Notifications.markRead(el.dataset.nid); refreshBell(); };
            el.onclick = open; el.onkeydown = (e) => e.key === "Enter" && open();
        });
        refreshSidebarCounts();
    }
    function refreshSidebarCounts() {
        const portal = document.body.dataset.portal;
        NAV[portal]?.filter((i) => i.count).forEach((i) => { const el = UI.$(`[data-count-for="${i.id}"]`); if (el) { const n = i.count(); el.textContent = n; el.hidden = !n; } });
    }

    /* ---------- Global search (staff) ---------- */
    function initSearch() {
        const input = UI.$("#gSearch"), box = UI.$("#gResults");
        if (!input) return;
        let hl = -1;
        const mark = (t, q) => UI.esc(t).replace(new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "ig"), "<mark>$1</mark>");
        function search() {
            const q = input.value.trim();
            if (q.length < 2) { box.classList.remove("open"); return; }
            const ql = q.toLowerCase();
            const has = (...f) => f.join(" ").toLowerCase().includes(ql);
            const groups = [
                ["Students", Students.all().filter((s) => has(s.firstName, s.lastName, s.id, s.email)).slice(0, 5).map((s) => ({ href: `students.html?id=${encodeURIComponent(s.id)}`, icon: "fa-user-graduate", tone: "", title: Students.fullName(s), sub: `${s.id} · ${Programmes.name(s.programmeId)}` }))],
                ["Applications", Applications.all().filter((a) => has(a.firstName, a.lastName, a.id, a.email)).slice(0, 5).map((a) => ({ href: `applications.html?id=${encodeURIComponent(a.id)}`, icon: "fa-file-signature", tone: "cyan", title: `${a.firstName} ${a.lastName}`, sub: `${a.id} · ${a.status}` }))],
                ["Payments & transactions", Payments.all().filter((p) => has(p.ref, p.name, p.applicationId)).slice(0, 5).map((p) => ({ href: `payments.html?ref=${encodeURIComponent(p.ref)}`, icon: "fa-naira-sign", tone: "green", title: p.ref, sub: `${p.name} · ${UI.naira(p.amount)} · ${p.status}` }))],
                ["Programmes", Programmes.all().filter((p) => has(p.name, p.code, p.track)).slice(0, 4).map((p) => ({ href: `programmes.html?id=${p.id}`, icon: "fa-layer-group", tone: "gold", title: p.name, sub: `${p.code} · ${UI.naira(p.fee)} · ${p.weeks} weeks` }))]
            ].filter(([, r]) => r.length);
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
        UI.$("#umTour").onclick = () => App.explore();
        // Dropdowns
        UI.$$(".dropdown").forEach((dd) => {
            const btn = dd.querySelector("button");
            btn.addEventListener("click", (e) => { e.stopPropagation(); const open = !dd.classList.contains("open"); UI.$$(".dropdown.open").forEach((x) => x.classList.remove("open")); dd.classList.toggle("open", open); btn.setAttribute("aria-expanded", open); });
        });
        document.addEventListener("click", (e) => { if (!e.target.closest(".dropdown")) UI.$$(".dropdown.open").forEach((x) => x.classList.remove("open")); });
        document.addEventListener("keydown", (e) => { if (e.key === "Escape") UI.$$(".dropdown.open").forEach((x) => x.classList.remove("open")); });
        UI.$("#bellReadAll").onclick = (e) => { e.stopPropagation(); Notifications.markAll(); refreshBell(); };
        refreshBell();
        initSearch();
    }

    return { NAV, chart, seedNoise, mount, refreshBell, refreshSidebarCounts };
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

/* ---------------- Staff dashboard ---------------- */
Pages["staff-dashboard"] = function (view, { session }) {
    const A = Applications.all(), S = Students.all(), P = Payments.all(), B = DB.settings().baselines || {};
    const revenueLive = P.filter((p) => p.status === "SUCCESS").reduce((t, p) => t + p.amount, 0);
    const k = {
        apps: A.length + (B.applications || 0),
        paid: A.filter((a) => a.paymentStatus === "Paid").length + (B.paid || 0),
        active: S.filter((s) => s.status === "Active").length + (B.active || 0),
        pending: A.filter((a) => ["Pending", "Under Review"].includes(a.status)).length + (B.pending || 0),
        revenue: revenueLive + (B.revenue || 0)
    };
    const attRecs = DB.all("attendance");
    const attAvg = attRecs.length ? Math.round(attRecs.filter((r) => r.status === "Present").length / attRecs.length * 100) : 0;
    const hr = new Date().getHours();
    const pendingReview = A.filter((a) => ["Pending", "Under Review", "Paid"].includes(a.status)).length;
    const schPending = DB.where("scholarships", (s) => s.status === "Pending").length;

    view.innerHTML = `
        <div class="welcome"><div style="position:relative;z-index:1"><span class="badge badge-primary no-dot">${UI.dateLong(new Date())}</span><h2>${hr < 12 ? "Good morning" : hr < 17 ? "Good afternoon" : "Good evening"}, ${UI.esc(session.name.split(" ").slice(0, 2).join(" "))}</h2>
            <p>${TSCE_FLYER.campaign}: <b>${pendingReview}</b> applications need attention and <b>${schPending}</b> scholarship requests await review. Classes begin <b>${UI.date(TSCE_FLYER.startDate, { weekday: "long", day: "numeric", month: "long" })}</b>.</p></div>
            <div class="actions"><a class="btn btn-primary" href="applications.html"><i class="fa-solid fa-file-signature"></i> Review applications</a><a class="btn btn-outline" href="reports.html"><i class="fa-solid fa-chart-pie"></i> Reports</a></div></div>
        <div class="kpis">
            ${[["Total Applications", k.apps, "", "fa-file-signature", "", "12.4%", "up"], ["Paid Applications", k.paid, "", "fa-circle-check", "green", "9.1%", "up"], ["Active Students", k.active, "", "fa-user-graduate", "cyan", "6.8%", "up"], ["Pending Applications", k.pending, "", "fa-hourglass-half", "gold", "3 today", "flat"], ["Revenue", k.revenue, "naira", "fa-naira-sign", "grad", "18.2%", "up"], ["Attendance Average", attAvg, "%", "fa-calendar-check", "green", "1.2%", "up"]]
            .map(([l, v, f, i, c, t, d]) => `<div class="kpi"><div class="kpi-top"><p class="label">${l}</p><span class="icon-tile ${c}"><i class="fa-solid ${i}"></i></span></div><div class="value" data-count="${v}" ${f === "naira" ? 'data-format="naira"' : f === "%" ? 'data-suffix="%"' : ""}>0</div><span class="trend ${d}"><i class="fa-solid ${d === "up" ? "fa-arrow-trend-up" : "fa-minus"}"></i> ${t}</span><span class="trend-note">vs last intake</span></div>`).join("")}
        </div>
        <div class="dash-grid cols-12">
            <div class="panel span-8"><div class="panel-head"><div><h3><i class="fa-solid fa-chart-line"></i>Revenue by month</h3><p>Verified Zainpay collections (₦)</p></div><span class="badge badge-success no-dot">${UI.naira(k.revenue, { compact: true })} total</span></div><div class="panel-body"><div class="chart-box"><canvas id="revChart"></canvas></div></div></div>
            <div class="panel span-4"><div class="panel-head"><div><h3><i class="fa-solid fa-chart-pie"></i>Payment status</h3><p>Current intake transactions</p></div></div><div class="panel-body"><div class="chart-box sm"><canvas id="payStatus"></canvas></div><div class="legend-list" id="payLegend"></div></div></div>
            <div class="panel span-7"><div class="panel-head"><div><h3><i class="fa-solid fa-chart-bar"></i>Applications by programme</h3><p>All-time applications per programme</p></div></div><div class="panel-body"><div class="chart-box lg"><canvas id="appsByProg"></canvas></div></div></div>
            <div class="panel span-5"><div class="panel-head"><div><h3><i class="fa-solid fa-filter"></i>Admissions funnel</h3><p>Current intake (${UI.esc(DB.settings().admissions?.intake || "")})</p></div></div><div class="panel-body" id="funnel"></div></div>
            <div class="panel span-6"><div class="panel-head"><div><h3><i class="fa-solid fa-users"></i>Student enrollment</h3><p>New students per cohort</p></div></div><div class="panel-body"><div class="chart-box sm"><canvas id="enrolChart"></canvas></div></div></div>
            <div class="panel span-6"><div class="panel-head"><div><h3><i class="fa-solid fa-calendar-check"></i>Attendance trend</h3><p>Weekly attendance rate — active cohorts</p></div></div><div class="panel-body"><div class="chart-box sm"><canvas id="attTrend"></canvas></div></div></div>
            <div class="panel span-7"><div class="panel-head"><h3><i class="fa-solid fa-clock-rotate-left"></i>Recent applications</h3><a class="btn btn-sm btn-ghost" href="applications.html">View all <i class="fa-solid fa-arrow-right"></i></a></div><ul class="list" id="recentApps"></ul></div>
            <div class="panel span-5"><div class="panel-head"><h3><i class="fa-solid fa-receipt"></i>Latest transactions</h3><a class="btn btn-sm btn-ghost" href="payments.html">View all <i class="fa-solid fa-arrow-right"></i></a></div><ul class="list" id="recentTx"></ul></div>
        </div>`;
    UI.animateAll(view);

    // Revenue by month: archived baseline spread across months + live collections
    const months = ["2026-03", "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"];
    const w = [.06, .09, .13, .18, .16, .21, .17];
    const live = months.map((m) => P.filter((p) => p.status === "SUCCESS" && p.createdAt.slice(0, 7) === m).reduce((t, p) => t + p.amount, 0));
    const rev = months.map((m, i) => Math.round((B.revenue || 0) * w[i]) + live[i]);
    Dashboard.chart("revChart", { type: "line", data: { labels: months.map((m) => UI.date(m + "-01", { month: "short", year: "2-digit" })), datasets: [{ label: "Revenue", data: rev, borderColor: "#1846D6", backgroundColor: (ctx) => { const g = ctx.chart.ctx.createLinearGradient(0, 0, 0, 280); g.addColorStop(0, "rgba(24,70,214,.25)"); g.addColorStop(1, "rgba(24,70,214,0)"); return g; }, fill: true, tension: .4, pointRadius: 4, pointBackgroundColor: "#fff", pointBorderWidth: 2 }] }, options: { plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => UI.naira(c.raw) } } }, scales: { y: { ticks: { callback: (v) => UI.naira(v, { compact: true }) } } } } });

    const st = ["SUCCESS", "PENDING", "FAILED", "REFUNDED"], colors = ["#12A150", "#F5B400", "#DC2F45", "#06C8E0"];
    const counts = st.map((x) => P.filter((p) => p.status === x).length);
    Dashboard.chart("payStatus", { type: "doughnut", data: { labels: st, datasets: [{ data: counts, backgroundColor: colors, borderWidth: 0 }] }, options: { cutout: "70%", plugins: { legend: { display: false } } } });
    UI.$("#payLegend").innerHTML = st.map((x, i) => `<div><i style="background:${colors[i]}"></i>${x.charAt(0) + x.slice(1).toLowerCase()}<b>${counts[i]}</b></div>`).join("");

    // Applications by programme: live + baseline distributed by historical enrolment weights
    const progs = Programmes.all();
    const wsum = progs.reduce((t, p) => t + p.enrolled, 0);
    let remaining = B.applications || 0;
    const byProg = progs.map((p, i) => { const base = i === progs.length - 1 ? remaining : Math.round((B.applications || 0) * p.enrolled / wsum); remaining -= base; return base + A.filter((a) => a.programmeId === p.id).length; });
    const order = byProg.map((v, i) => i).sort((a, b) => byProg[b] - byProg[a]);
    Dashboard.chart("appsByProg", { type: "bar", data: { labels: order.map((i) => progs[i].name.length > 26 ? progs[i].name.slice(0, 24) + "…" : progs[i].name), datasets: [{ data: order.map((i) => byProg[i]), backgroundColor: order.map((i) => progs[i].color), borderRadius: 6, maxBarThickness: 18 }] }, options: { indexAxis: "y", plugins: { legend: { display: false } } } });

    // Enrollment by cohort
    const cohorts = [["Jan 2026", 38], ["Mar 2026", 46], ["Jun 2026", 0], ["Aug–Sep 2026", 0], ["Oct 2026", 0]];
    const liveBy = (c) => S.filter((s) => s.cohort.startsWith(c)).length;
    const enrol = [38, 46, 52 + liveBy("July"), 61 + liveBy("August") + liveBy("September"), liveBy("October") + A.filter((a) => a.intake.startsWith("October") && a.paymentStatus === "Paid").length];
    Dashboard.chart("enrolChart", { type: "bar", data: { labels: cohorts.map((c) => c[0]), datasets: [{ label: "Students", data: enrol, backgroundColor: ["#DCE6FF", "#B9CCFF", "#7DA0FF", "#1846D6", "#06C8E0"], borderRadius: 8, maxBarThickness: 44 }] }, options: { plugins: { legend: { display: false } } } });

    // Attendance trend (weekly, last 8 weeks)
    const weeks = Array.from({ length: 8 }, (_, i) => { const d = new Date(); d.setDate(d.getDate() - (7 - i) * 7); return d; });
    const wk = weeks.map((d) => { const end = new Date(d); end.setDate(end.getDate() + 7); const rs = attRecs.filter((r) => new Date(r.date) >= d && new Date(r.date) < end); return rs.length ? Math.round(rs.filter((r) => r.status !== "Absent").length / rs.length * 100) : null; });
    Dashboard.chart("attTrend", { type: "line", data: { labels: weeks.map((d) => UI.date(d, { day: "numeric", month: "short" })), datasets: [{ label: "Attendance %", data: wk, borderColor: "#12A150", backgroundColor: "rgba(18,161,80,.12)", fill: true, tension: .4, spanGaps: true, pointRadius: 3 }, { label: "Target (75%)", data: weeks.map(() => 75), borderColor: "#DC2F45", borderDash: [6, 5], pointRadius: 0, borderWidth: 1.5 }] }, options: { scales: { y: { min: 60, max: 100, ticks: { callback: (v) => v + "%" } } } } });

    // Funnel (current intake)
    const cur = A.filter((a) => a.intake === DB.settings().admissions?.intake);
    const f = [["Applied", cur.length, "#1846D6"], ["Paid", cur.filter((a) => a.paymentStatus === "Paid").length, "#0EA5E9"], ["Under review", cur.filter((a) => a.status === "Under Review").length, "#F5B400"], ["Accepted / Enrolled", cur.filter((a) => ["Accepted", "Enrolled"].includes(a.status)).length, "#12A150"]];
    UI.$("#funnel").innerHTML = f.map(([l, v, c]) => `<div class="mb-2"><div class="flex between small mb-1"><span style="font-weight:600">${l}</span><b>${v}</b></div><div class="progress" style="height:12px"><span data-value="${cur.length ? v / cur.length * 100 : 0}" style="background:${c}"></span></div></div>`).join("") + `<a class="btn btn-soft btn-sm mt-1" href="applications.html?status=Paid">Paid applications awaiting approval →</a>`;
    UI.progressBars(UI.$("#funnel"));

    UI.$("#recentApps").innerHTML = [...A].sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt)).slice(0, 5).map((a) => `<li class="list-item" style="cursor:pointer" data-app="${UI.esc(a.id)}">${UI.avatar(a.firstName + " " + a.lastName, "sm")}<div class="grow"><strong>${UI.esc(a.firstName + " " + a.lastName)}</strong><small>${UI.esc(Programmes.name(a.programmeId))} · ${UI.timeAgo(a.createdAt)}</small></div>${UI.badge(a.status)}</li>`).join("");
    UI.$$("[data-app]").forEach((li) => li.onclick = () => location.href = `applications.html?id=${encodeURIComponent(li.dataset.app)}`);
    UI.$("#recentTx").innerHTML = [...P].sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt)).slice(0, 5).map((p) => `<li class="list-item" style="cursor:pointer" data-tx="${UI.esc(p.ref)}"><span class="icon-tile ${p.status === "SUCCESS" ? "green" : p.status === "FAILED" ? "red" : "gold"}"><i class="fa-solid fa-naira-sign"></i></span><div class="grow"><strong>${UI.naira(p.amount)}</strong><small>${UI.esc(p.name)} · ${UI.timeAgo(p.createdAt)}</small></div>${UI.badge(p.status)}</li>`).join("");
    UI.$$("[data-tx]").forEach((li) => li.onclick = () => location.href = `payments.html?ref=${encodeURIComponent(li.dataset.tx)}`);
};

/* ---------------- Staff directory (admin) ---------------- */
Pages["staff-staff"] = function (view) {
    view.innerHTML = `<div class="view-head"><div><h2>Staff</h2><p>Instructors, admissions, finance and management team.</p></div><div class="actions"><button class="btn btn-primary" id="addStaff"><i class="fa-solid fa-user-plus"></i> Add staff</button></div></div>
        <div class="kpis" id="sfK"></div><div class="panel"><div class="table-tools"><div class="input-icon"><i class="fa-solid fa-magnifying-glass"></i><input class="input" id="sfQ" placeholder="Search staff…" aria-label="Search staff"></div><select class="select" id="sfD" aria-label="Department"><option value="">All departments</option><option>Management</option><option>Admissions</option><option>Finance</option><option>Academics</option></select></div><div id="sfT"></div></div>`;
    const t = UI.dataTable("#sfT", {
        pageSize: 10,
        onRender: (el) => UI.$$("[data-sft]", el).forEach((b) => b.onclick = (e) => { e.stopPropagation(); const s = DB.get("staff", b.dataset.sft); DB.update("staff", s.id, { status: s.status === "Active" ? "Inactive" : "Active" }); UI.toast("Staff status updated", s.name, "success"); refresh(); }),
        columns: [
            { key: "name", label: "Name", render: (s) => `<div class="person">${UI.avatar(s.name, "sm")}<div><strong>${UI.esc(s.name)}</strong><small>${UI.esc(s.email)}</small></div></div>` },
            { key: "title", label: "Role" }, { key: "department", label: "Department", render: (s) => `<span class="badge badge-neutral no-dot">${UI.esc(s.department)}</span>` },
            { key: "phone", label: "Phone" }, { key: "role", label: "Access", render: (s) => `<span class="badge ${s.role === "admin" ? "badge-dark" : "badge-primary"} no-dot">${s.role}</span>` },
            { key: "status", label: "Status", render: (s) => UI.badge(s.status) },
            { key: "", label: "", sortable: false, render: (s) => s.role === "admin" ? "" : `<button class="btn btn-xs btn-ghost" data-sft="${s.id}">${s.status === "Active" ? "Deactivate" : "Activate"}</button>` }
        ]
    });
    function refresh() {
        const S = DB.all("staff"), q = UI.$("#sfQ").value.toLowerCase(), d = UI.$("#sfD").value;
        UI.$("#sfK").innerHTML = [["Total staff", S.length, "fa-id-badge", ""], ["Instructors", S.filter((s) => s.department === "Academics").length, "fa-chalkboard-user", "cyan"], ["Active", S.filter((s) => s.status === "Active").length, "fa-user-check", "green"], ["On leave / inactive", S.filter((s) => s.status !== "Active").length, "fa-plane-departure", "gold"]].map(([l, v, i, c]) => `<div class="kpi"><div class="kpi-top"><p class="label">${l}</p><span class="icon-tile ${c}"><i class="fa-solid ${i}"></i></span></div><div class="value">${v}</div></div>`).join("");
        t.update(S.filter((s) => (!d || s.department === d) && (s.name + s.title + s.email).toLowerCase().includes(q)), { resetPage: false });
    }
    UI.$("#sfQ").oninput = UI.debounce(refresh, 150); UI.$("#sfD").onchange = refresh;
    UI.$("#addStaff").onclick = () => {
        const m = UI.modal({ title: "Add staff member", size: "lg", body: `<form id="asf" class="form-grid" novalidate>
            <div class="field"><label for="as_n">Full name <span class="req">*</span></label><input id="as_n" name="name" class="input" required></div>
            <div class="field"><label for="as_t">Job title <span class="req">*</span></label><input id="as_t" name="title" class="input" required></div>
            <div class="field"><label for="as_e">Email <span class="req">*</span></label><input id="as_e" name="email" type="email" class="input" required placeholder="name@tsce.edu.ng"></div>
            <div class="field"><label for="as_p">Phone <span class="req">*</span></label><input id="as_p" name="phone" class="input" data-type="phone" required></div>
            <div class="field"><label for="as_d">Department</label><select id="as_d" name="department" class="select"><option>Academics</option><option>Admissions</option><option>Finance</option><option>Management</option></select></div>
            <div class="field"><label for="as_r">Portal access</label><select id="as_r" name="role" class="select"><option value="staff">Staff</option><option value="admin">Admin</option></select></div></form><p class="hint mt-2">A temporary password (<b>staff123</b>) is created for the demo.</p>`,
            footer: `<button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-primary" id="asSave">Add staff</button>` });
        UI.liveValidate(UI.$("#asf", m.el));
        UI.$("#asSave", m.el).onclick = () => {
            const f = UI.$("#asf", m.el); if (!UI.validate(f)) return;
            const d = UI.formData(f);
            if (DB.first("users", (u) => u.email === d.email.toLowerCase())) return UI.fieldError(UI.$("#as_e", m.el), "This email is already in use.");
            const id = "STF-" + String(DB.all("staff").length + 1).padStart(3, "0");
            DB.insert("staff", { id, ...d, email: d.email.toLowerCase(), status: "Active", joined: new Date().toISOString() }, { prepend: false });
            DB.insert("users", { email: d.email.toLowerCase(), password: "staff123", role: d.role, name: d.name, staffId: id });
            m.close(); UI.toast("Staff added", `${d.name} can sign in with staff123`, "success"); refresh();
        };
    };
    refresh();
};

/* ---------------- Staff settings (admin) ---------------- */
Pages["staff-settings"] = function (view) {
    const s = DB.settings();
    const inst = s.institution || {}, adm = s.admissions || {}, pay = s.payments || {}, nt = s.notifications || {};
    const sw = (k, sec, v, l, d) => `<div class="setting-row"><div><strong>${l}</strong><small>${d}</small></div><label class="switch"><input type="checkbox" data-sec="${sec}" name="${k}" ${v ? "checked" : ""} aria-label="${l}"><span></span></label></div>`;
    view.innerHTML = `<div class="view-head"><div><h2>Settings</h2><p>Configure the institution profile, admissions calendar, payment gateway and notifications.</p></div></div>
        <div class="settings-layout">
            <nav class="panel settings-nav" aria-label="Settings sections">${[["inst", "fa-building-columns", "Institution"], ["adm", "fa-door-open", "Admissions"], ["pay", "fa-credit-card", "Payments"], ["notif", "fa-bell", "Notifications"], ["data", "fa-database", "Demo data"]].map(([id, i, t], k) => `<a href="#${id}" class="${k === 0 ? "active" : ""}"><i class="fa-solid ${i}"></i>${t}</a>`).join("")}</nav>
            <div style="display:grid;gap:20px">
                <form class="panel" id="inst" data-sec="institution"><div class="panel-head"><div><h3><i class="fa-solid fa-building-columns"></i>Institution</h3><p>Shown on receipts, certificates and the website</p></div></div><div class="panel-body"><div class="form-grid">
                    <div class="field span-2"><label for="i_n">Name</label><input id="i_n" name="name" class="input" value="${UI.esc(inst.name)}" required></div>
                    <div class="field span-2"><label for="i_a">Address</label><input id="i_a" name="address" class="input" value="${UI.esc(inst.address)}" required></div>
                    <div class="field"><label for="i_p">Phone</label><input id="i_p" name="phone" class="input" value="${UI.esc(inst.phone)}"></div>
                    <div class="field"><label for="i_w">Website</label><input id="i_w" name="website" class="input" value="${UI.esc(inst.website)}"></div>
                    <div class="field"><label for="i_e">Email</label><input id="i_e" name="email" type="email" class="input" value="${UI.esc(inst.email)}"></div>
                    <div class="field"><label>Logo</label><div class="flex">${UI.logo("brand-mark")}<button type="button" class="btn btn-sm btn-outline" id="logoUp">Upload logo</button></div></div>
                </div></div><div class="table-foot"><span class="small muted">Values from the TSCE flyer are pre-filled.</span><button class="btn btn-primary">Save</button></div></form>
                <form class="panel" id="adm" data-sec="admissions"><div class="panel-head"><div><h3><i class="fa-solid fa-door-open"></i>Admissions</h3><p>Application window and cohort dates</p></div></div><div class="panel-body"><div class="form-grid">
                    <div class="field"><label for="a_o">Application opening date</label><input id="a_o" type="date" name="opens" class="input" value="${adm.opens}"></div>
                    <div class="field"><label for="a_c">Closing date</label><input id="a_c" type="date" name="closes" class="input" value="${adm.closes}"></div>
                    <div class="field"><label for="a_d">Cohort start date</label><input id="a_d" type="date" name="cohortDate" class="input" value="${adm.cohortDate}"></div>
                    <div class="field"><label for="a_e">Early-bird deadline (pay before)</label><input id="a_e" type="date" name="earlyBirdDeadline" class="input" value="${adm.earlyBirdDeadline}"></div>
                    <div class="field span-2"><label for="a_i">Current intake name</label><input id="a_i" name="intake" class="input" value="${UI.esc(adm.intake)}"></div>
                    <div class="span-2">${sw("acceptingApplications", "admissions", adm.acceptingApplications !== false, "Accept new applications", "Turn off to close the online application form")}</div>
                </div></div><div class="table-foot"><span></span><button class="btn btn-primary">Save</button></div></form>
                <form class="panel" id="pay" data-sec="payments"><div class="panel-head"><div><h3><i class="fa-solid fa-credit-card"></i>Payments</h3><p>Gateway and transaction settings</p></div><span class="badge badge-warning">Sandbox (simulated)</span></div><div class="panel-body"><div class="form-grid">
                    <div class="field"><label for="p_g">Gateway</label><select id="p_g" name="gateway" class="select"><option>Zainpay</option></select></div>
                    <div class="field"><label for="p_c">Currency</label><select id="p_c" name="currency" class="select"><option value="NGN">NGN — Nigerian Naira (₦)</option></select></div>
                    <div class="field"><label for="p_env">Environment</label><select id="p_env" name="environment" class="select"><option value="sandbox" ${pay.environment === "sandbox" ? "selected" : ""}>Sandbox</option><option value="live" disabled>Live (requires backend)</option></select></div>
                    <div class="field"><label for="p_r">Transaction reference prefix</label><input id="p_r" name="refPrefix" class="input" value="${UI.esc(pay.refPrefix)}"></div>
                    <div class="span-2">${sw("allowCard", "payments", pay.allowCard !== false, "Card payments", "Visa, Mastercard, Verve")}${sw("allowTransfer", "payments", pay.allowTransfer !== false, "Bank transfer", "Pay into the Zainpay collection account")}${sw("allowVirtual", "payments", pay.allowVirtual !== false, "Virtual accounts", "Dedicated account per applicant")}${sw("autoVerify", "payments", pay.autoVerify !== false, "Auto-verify transactions", "Verify every payment with the gateway before giving value")}</div>
                    <div class="span-2 alert"><i class="fa-solid fa-lock"></i><p>Zainpay API keys are configured on the server only. This frontend never stores secret credentials.</p></div>
                </div></div><div class="table-foot"><span></span><button class="btn btn-primary">Save</button></div></form>
                <form class="panel" id="notif" data-sec="notifications"><div class="panel-head"><div><h3><i class="fa-solid fa-bell"></i>Notifications</h3><p>Channels used for applicant and student messages</p></div></div><div class="panel-body">
                    ${sw("email", "notifications", nt.email, "Email", "Receipts, admission letters, results")}${sw("sms", "notifications", nt.sms, "SMS", "Payment and class reminders")}${sw("push", "notifications", nt.push, "Push notifications", "Browser/app push (future)")}${sw("paymentAlerts", "notifications", nt.paymentAlerts, "Staff payment alerts", "Notify finance of every payment")}${sw("applicationAlerts", "notifications", nt.applicationAlerts, "Staff application alerts", "Notify admissions of new applications")}
                </div><div class="table-foot"><span></span><button class="btn btn-primary">Save</button></div></form>
                <div class="panel" id="data"><div class="panel-head"><div><h3><i class="fa-solid fa-database"></i>Demo data</h3><p>All records are stored in this browser (localStorage)</p></div></div><div class="panel-body">
                    <div class="setting-row"><div><strong>Reset demo data</strong><small>Restore the original demo students, applications and payments. Your changes will be lost.</small></div><button class="btn btn-soft-danger" id="resetData"><i class="fa-solid fa-rotate-left"></i> Reset</button></div>
                    <div class="setting-row"><div><strong>Export all data</strong><small>Download a JSON backup of every collection.</small></div><button class="btn btn-outline" id="dumpData"><i class="fa-solid fa-download"></i> Export JSON</button></div>
                </div></div>
            </div></div>`;
    UI.$$("form[data-sec]").forEach((f) => f.addEventListener("submit", (e) => {
        e.preventDefault();
        if (!UI.validate(f)) return;
        const sec = f.dataset.sec, d = UI.formData(f);
        UI.$$('input[type="checkbox"]', f).forEach((c) => d[c.name] = c.checked);
        DB.saveSettings({ [sec]: d });
        UI.toast("Settings saved", `${sec.charAt(0).toUpperCase() + sec.slice(1)} settings updated.`, "success");
    }));
    UI.$$(".settings-nav a").forEach((a) => a.onclick = (e) => { e.preventDefault(); UI.$$(".settings-nav a").forEach((x) => x.classList.toggle("active", x === a)); UI.$(a.getAttribute("href")).scrollIntoView({ behavior: "smooth", block: "start" }); });
    UI.$("#logoUp").onclick = () => UI.toast("Logo upload", "The official TSCE logo is in assets/logo/ (tsce-emblem.png, tsce-logo-full.png). Replace those files to update it everywhere.", "info");
    UI.$("#resetData").onclick = async () => { if (!(await UI.confirm({ title: "Reset all demo data?", message: "Everything returns to the original demo state. You'll stay signed in.", confirmText: "Reset data", tone: "danger", icon: "fa-rotate-left" }))) return; const sess = DB.session.get(); DB.reset(); DB.session.set(sess); UI.toast("Demo data reset", "Reloading…", "success"); setTimeout(() => location.reload(), 700); };
    UI.$("#dumpData").onclick = () => { const out = {}; ["users", "students", "applications", "payments", "programmes", "attendance", "results", "scholarships", "staff", "announcements", "notifications", "settings"].forEach((k) => out["tsce_" + k] = k === "settings" ? DB.settings() : DB.all(k)); const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 2)], { type: "application/json" })); a.download = "tsce-demo-data.json"; a.click(); UI.toast("Export ready", "tsce-demo-data.json downloaded", "success"); };
};
