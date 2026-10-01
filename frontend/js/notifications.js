/* ==========================================================================
   TSCE — Notifications & Announcements
   Notifications are addressed to an email (student/applicant) or "staff".
   BACKEND INTEGRATION POINT: push() would enqueue email/SMS/push jobs.
   ========================================================================== */

const Notifications = (() => {
    const ICON = { application: ["fa-file-lines", ""], payment: ["fa-naira-sign", "green"], scholarship: ["fa-award", "gold"], result: ["fa-chart-simple", "cyan"], announcement: ["fa-bullhorn", ""], attendance: ["fa-calendar-check", "cyan"], certificate: ["fa-certificate", "gold"], support: ["fa-headset", ""] };

    function push(to, title, body, type = "announcement") {
        if (!to) return;
        DB.insert("notifications", { id: "NTF-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 5), to, title, body, type, read: false, createdAt: new Date().toISOString() });
    }
    const keyFor = (s = Auth.current()) => !s ? null : s.role === "student" || s.role === "applicant" ? s.email : "staff";
    const list = (key = keyFor()) => DB.where("notifications", (n) => n.to === key).sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
    const unread = (key = keyFor()) => list(key).filter((n) => !n.read).length;
    function markRead(id) { DB.update("notifications", id, { read: true }); }
    function markAll(key = keyFor()) { DB.save("notifications", DB.all("notifications").map((n) => n.to === key ? { ...n, read: true } : n)); }

    function itemHTML(n) {
        const [ic, tone] = ICON[n.type] || ICON.announcement;
        return `<div class="notif ${n.read ? "" : "unread"}" data-nid="${n.id}" tabindex="0" role="button"><span class="icon-tile ${tone}"><i class="fa-solid ${ic}"></i></span><div><div class="n-title">${UI.esc(n.title)}</div><p>${UI.esc(n.body)}</p><small>${UI.timeAgo(n.createdAt)}</small></div></div>`;
    }
    return { ICON, push, keyFor, list, unread, markRead, markAll, itemHTML };
})();

const Announcements = (() => {
    const all = () => DB.all("announcements").sort((a, b) => (b.pinned - a.pinned) || new Date(b.createdAt) - new Date(a.createdAt));
    const visibleTo = (aud) => all().filter((a) => a.status === "Published" && (a.audience === "All" || a.audience === "Public" || a.audience === aud));
    const TAG_ICON = { Event: "fa-calendar-star", Admissions: "fa-door-open", Scholarship: "fa-award", Academic: "fa-book-open", Facilities: "fa-building", Internal: "fa-lock", News: "fa-newspaper", Certificates: "fa-certificate" };
    const iconFor = (t) => TAG_ICON[t] || "fa-bullhorn";
    function itemHTML(a, { admin = false } = {}) {
        return `<div class="ann ${a.pinned ? "pinned" : ""}" data-aid="${a.id}">
            <span class="icon-tile ${a.pinned ? "gold" : ""}"><i class="fa-solid ${iconFor(a.tag).replace("fa-calendar-star", "fa-calendar-days")}"></i></span>
            <div><h4>${a.pinned ? '<i class="fa-solid fa-thumbtack" style="color:var(--gold);font-size:.8rem;margin-right:6px"></i>' : ""}${UI.esc(a.title)}</h4><p>${UI.esc(a.body)}</p>
                <div class="meta"><span><i class="fa-regular fa-calendar"></i> ${UI.date(a.createdAt)}</span><span><i class="fa-regular fa-user"></i> ${UI.esc(a.author)}</span><span class="badge badge-neutral no-dot">${UI.esc(a.tag)}</span>${admin ? `<span class="badge badge-info no-dot">${UI.esc(a.audience)}</span>` : ""}</div></div>
            <div class="row-actions">${admin ? `${UI.badge(a.status)}<button class="icon-btn" data-aedit="${a.id}" aria-label="Edit"><i class="fa-solid fa-pen"></i></button><button class="icon-btn danger" data-adel="${a.id}" aria-label="Delete"><i class="fa-solid fa-trash"></i></button>` : ""}</div></div>`;
    }
    return { all, visibleTo, iconFor, itemHTML };
})();

/* ---------------- Staff: Announcements ---------------- */
Pages["staff-announcements"] = function (view) {
    let filter = "";
    view.innerHTML = `
        <div class="view-head"><div><h2>Announcements</h2><p>Publish updates to students, staff and the public website.</p></div>
            <div class="actions"><button class="btn btn-primary" id="newAnn"><i class="fa-solid fa-plus"></i> New announcement</button></div></div>
        <div class="stat-chips" id="annChips"></div>
        <div class="panel" id="annList"></div>`;
    function render() {
        const A = Announcements.all();
        const defs = [["", "All", A.length], ["Published", "Published", A.filter((a) => a.status === "Published").length], ["Draft", "Drafts", A.filter((a) => a.status === "Draft").length], ["Students", "Students", A.filter((a) => a.audience === "Students").length], ["Public", "Public", A.filter((a) => a.audience === "Public").length], ["Staff", "Staff", A.filter((a) => a.audience === "Staff").length]];
        UI.$("#annChips").innerHTML = defs.map(([v, l, n]) => `<button class="stat-chip ${filter === v ? "active" : ""}" data-f="${v}">${l} <b>${n}</b></button>`).join("");
        UI.$$("#annChips .stat-chip").forEach((c) => c.onclick = () => { filter = c.dataset.f; render(); });
        const list = A.filter((a) => !filter || a.status === filter || a.audience === filter);
        UI.$("#annList").innerHTML = list.length ? list.map((a) => Announcements.itemHTML(a, { admin: true })).join("") : UI.empty({ icon: "fa-bullhorn", title: "No announcements", text: "Create an announcement to keep everyone informed.", action: `<button class="btn btn-primary" onclick="document.getElementById('newAnn').click()">New announcement</button>` });
        UI.$$("[data-aedit]").forEach((b) => b.onclick = () => edit(b.dataset.aedit));
        UI.$$("[data-adel]").forEach((b) => b.onclick = async () => {
            const a = DB.get("announcements", b.dataset.adel);
            if (!(await UI.confirm({ title: "Delete announcement?", message: `“${UI.esc(a.title)}” will be removed permanently.`, confirmText: "Delete", tone: "danger", icon: "fa-trash" }))) return;
            DB.remove("announcements", a.id); UI.toast("Announcement deleted", a.title, "success"); render();
        });
    }
    function edit(id) {
        const a = id ? DB.get("announcements", id) : { title: "", body: "", audience: "Students", tag: "News", pinned: false, status: "Published" };
        const m = UI.modal({
            title: id ? "Edit announcement" : "New announcement", size: "lg",
            body: `<form id="annForm" class="form-grid" novalidate>
                <div class="field span-2"><label for="an_t">Title <span class="req">*</span></label><input id="an_t" name="title" class="input" required value="${UI.esc(a.title)}" placeholder="e.g. October Cohort Orientation"></div>
                <div class="field span-2"><label for="an_b">Message <span class="req">*</span></label><textarea id="an_b" name="body" class="textarea" required minlength="10" placeholder="Write the announcement…">${UI.esc(a.body)}</textarea></div>
                <div class="field"><label for="an_a">Audience</label><select id="an_a" name="audience" class="select">${["Students", "Staff", "Public", "All"].map((x) => `<option ${a.audience === x ? "selected" : ""}>${x}</option>`).join("")}</select></div>
                <div class="field"><label for="an_g">Category</label><select id="an_g" name="tag" class="select">${["News", "Event", "Admissions", "Scholarship", "Academic", "Facilities", "Certificates", "Internal"].map((x) => `<option ${a.tag === x ? "selected" : ""}>${x}</option>`).join("")}</select></div>
                <label class="check span-2"><input type="checkbox" name="pinned" ${a.pinned ? "checked" : ""}> Pin to top</label>
                <label class="check span-2"><input type="checkbox" name="notify" checked> Send as notification to the audience</label>
            </form>`,
            footer: `<button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-outline" data-save="Draft">Save draft</button><button class="btn btn-primary" data-save="Published"><i class="fa-solid fa-paper-plane"></i> Publish</button>`
        });
        const f = UI.$("#annForm", m.el);
        UI.liveValidate(f);
        UI.$$("[data-save]", m.el).forEach((b) => b.onclick = () => {
            if (!UI.validate(f)) return;
            const d = UI.formData(f);
            const rec = { title: d.title, body: d.body, audience: d.audience, tag: d.tag, pinned: !!d.pinned, status: b.dataset.save };
            if (id) DB.update("announcements", id, rec);
            else DB.insert("announcements", { id: "ANN-" + Date.now().toString(36), ...rec, author: Auth.current()?.name || "Admin", createdAt: new Date().toISOString() });
            if (d.notify && rec.status === "Published") {
                if (["Students", "All"].includes(rec.audience)) DB.all("students").filter((s) => s.status !== "Completed").forEach((s) => Notifications.push(s.email, rec.title, rec.body.slice(0, 120), "announcement"));
                if (["Staff", "All"].includes(rec.audience)) Notifications.push("staff", rec.title, rec.body.slice(0, 120), "announcement");
            }
            m.close();
            UI.toast(rec.status === "Published" ? "Announcement published" : "Draft saved", rec.title, "success");
            render(); Dashboard.refreshBell();
        });
    }
    UI.$("#newAnn").onclick = () => edit(null);
    render();
};

/* ---------------- Student: Announcements ---------------- */
Pages["student-announcements"] = function (view) {
    const list = Announcements.visibleTo("Students");
    view.innerHTML = `<div class="view-head"><div><h2>Announcements</h2><p>Updates from TSCE management, admissions and your instructors.</p></div></div>
        <div class="dash-grid cols-12">
            <div class="panel span-8">${list.length ? list.map((a) => Announcements.itemHTML(a)).join("") : UI.empty({ icon: "fa-bullhorn", title: "No announcements yet", text: "New announcements will appear here." })}</div>
            <div class="panel span-4"><div class="panel-head"><h3><i class="fa-regular fa-bell"></i>Your notifications</h3><button class="btn btn-xs btn-ghost" id="readAll">Mark all read</button></div><div id="myNotifs"></div></div>
        </div>`;
    function notifs() {
        const n = Notifications.list();
        UI.$("#myNotifs").innerHTML = n.length ? n.map(Notifications.itemHTML).join("") : UI.empty({ icon: "fa-bell-slash", title: "You're all caught up" });
        UI.$$("#myNotifs [data-nid]").forEach((el) => el.onclick = () => { Notifications.markRead(el.dataset.nid); notifs(); Dashboard.refreshBell(); });
    }
    UI.$("#readAll").onclick = () => { Notifications.markAll(); notifs(); Dashboard.refreshBell(); };
    notifs();
};

/* ---------------- Public: News & Events ---------------- */
Pages["news"] = function () {
    const grads = ["linear-gradient(135deg,#1846D6,#06C8E0)", "linear-gradient(135deg,#0B1D55,#1846D6)", "linear-gradient(135deg,#F5B400,#F97316)", "linear-gradient(135deg,#12A150,#0EA5E9)", "linear-gradient(135deg,#7C3AED,#1846D6)"];
    const list = Announcements.all().filter((a) => a.status === "Published" && (a.audience === "Public" || a.audience === "All"));
    const events = [
        { d: "1", m: "Oct", t: "Registration Opens", s: "Online applications & payments via Zainpay" },
        { d: "3–7", m: "Oct", t: "Intake Exams & Interviews", s: "For Performance Scholarship candidates" },
        { d: "10", m: "Oct", t: "Orientation", s: "For all newly admitted students" },
        { d: "12", m: "Oct", t: "Classes Commence", s: "Monday, 12th October 2026" }
    ];
    UI.$("#newsGrid").innerHTML = list.map((a, i) => `<article class="news-card card-hover reveal"><div class="news-thumb" style="background:${grads[i % grads.length]}"><i class="fa-solid ${Announcements.iconFor(a.tag).replace("fa-calendar-star", "fa-calendar-days")}" style="position:relative;z-index:1"></i></div>
        <div class="news-body"><div class="news-meta"><span class="badge badge-primary no-dot">${UI.esc(a.tag)}</span><span>${UI.date(a.createdAt)}</span></div><h3>${UI.esc(a.title)}</h3><p>${UI.esc(a.body)}</p><button class="link-btn" data-read="${a.id}">Read more <i class="fa-solid fa-arrow-right"></i></button></div></article>`).join("") || UI.empty({ icon: "fa-newspaper", title: "No news yet" });
    UI.$("#eventList").innerHTML = events.map((e) => `<div class="tl-item reveal"><div class="tl-date"><b>${e.d}</b><small>${e.m}</small></div><div><h4>${e.t}</h4><p>${e.s}</p></div></div>`).join("");
    UI.$$("[data-read]").forEach((b) => b.onclick = () => { const a = DB.get("announcements", b.dataset.read); UI.modal({ title: UI.esc(a.title), subtitle: `${UI.date(a.createdAt)} · ${UI.esc(a.author)}`, body: `<p>${UI.esc(a.body)}</p>`, footer: `<a class="btn btn-primary" href="application.html">Apply now</a>` }); });
    UI.animateAll();
};
