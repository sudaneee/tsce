/* ==========================================================================
   TSCE — Staff portal pages backed by the API (Phase 5)
   Dashboard · Applications · Excellence Awards · Payments · Staff · Settings
   Loaded on staff pages after the older modules, so these definitions win.
   ========================================================================== */

const Staff = (() => {
    const STATUSES = ["Pending", "Awaiting Verification", "Admitted", "Enrolled", "Rejected"];
    const STEPS = ["Applied", "Application fee", "Admission", "Programme fee", "Enrolled"];
    const STAGE = { Pending: 1, "Awaiting Verification": 2, Admitted: 3, Enrolled: 5, Rejected: 2 };
    const PURPOSE = { application_fee: "Application fee", programme_fee: "Programme fee" };
    const fail = (title) => (e) => UI.toast(title, e.message, "error", 7000);
    const enc = encodeURIComponent;

    function lifecycle(a) {
        const idx = STAGE[a.status] ?? 1, rejected = a.status === "Rejected";
        return `<div class="lifecycle">${STEPS.map((s, i) => {
            const bad = rejected && i === 2, done = i < idx && !bad, cur = !rejected && i === idx;
            return `<div class="lc-step ${done ? "done" : cur ? "current" : ""} ${bad ? "bad" : ""}"><div class="c">${done ? '<i class="fa-solid fa-check"></i>' : bad ? '<i class="fa-solid fa-xmark"></i>' : i + 1}</div>${bad ? "Rejected" : s}</div>`;
        }).join("")}</div>`;
    }

    /** Application detail drawer with the staff actions that fit its status. */
    async function openApplication(number, onChange = () => { }) {
        let a;
        try { a = await API.get(`staff/applications/${enc(number)}`); }
        catch (e) { return fail("Couldn't open application")(e); }
        const kv = (k, v, full) => `<div class="${full ? "full" : ""}"><small>${k}</small><strong>${v}</strong></div>`;
        const award = a.awardRequest;
        const acts = [];
        if (a.status === "Awaiting Verification" && award?.status === "Pending") {
            acts.push(`<button class="btn btn-soft-danger" data-act="award-no"><i class="fa-solid fa-xmark"></i> Decline award</button>`,
                `<button class="btn btn-success" data-act="award-yes"><i class="fa-solid fa-award"></i> Approve award (${award.requestedPct}%)</button>`);
        }
        if (["Pending", "Admitted"].includes(a.status)) acts.push(`<button class="btn btn-outline" data-act="remind"><i class="fa-regular fa-bell"></i> Send reminder</button>`);
        if (!["Enrolled", "Rejected"].includes(a.status)) acts.push(`<button class="btn btn-ghost" data-act="reject" style="color:var(--danger)"><i class="fa-solid fa-ban"></i> Reject</button>`);

        const d = UI.drawer({
            title: UI.esc(a.name), subtitle: `<span class="mono">${UI.esc(a.id)}</span> · ${UI.badge(a.status)}`,
            body: `${lifecycle(a)}
                ${a.status === "Awaiting Verification" ? `<div class="alert warning mb-2"><i class="fa-solid fa-id-card"></i><p><b>Excellence Award to verify.</b> Check the <b>original</b> WAEC/NECO result in person: ${UI.esc(award?.evidence || "")}. Approving or declining admits the applicant; declining means the normal fee.</p></div>` : ""}
                <div class="dr-section"><h4>Programme & fees</h4><div class="kv">
                    ${kv("Programme", UI.esc(a.programmeName), true)}${kv("Schedule", UI.esc(a.schedule))}${kv("Intake", UI.esc(a.intake))}
                    ${kv("Application fee", a.applicationFeePaidAt ? `${UI.naira(a.applicationFee)} · paid ${UI.date(a.applicationFeePaidAt)}` : `${UI.naira(a.applicationFee)} · unpaid`)}
                    ${kv("Programme fee", `${UI.naira(a.amountPayable)}${a.discountAmount ? ` <span class="small muted">(${Applications.discountName(a.discountType)} −${UI.naira(a.discountAmount)})</span>` : ""} · ${UI.esc(a.paymentStatus)}`)}
                    ${award ? kv("Excellence Award", `${UI.badge(award.status)} ${award.awardedPct ? `${award.awardedPct}%` : ""} ${award.note ? `<span class="small muted">— ${UI.esc(award.note)}</span>` : ""}`, true) : ""}
                    ${a.studentId ? kv("Student number", `<span class="mono">${UI.esc(a.studentId)}</span>`) : ""}
                </div></div>
                <div class="dr-section"><h4>Applicant</h4><div class="kv">
                    ${kv("Gender", UI.esc(a.gender))}${kv("Date of birth", UI.date(a.dob))}
                    ${kv("Phone", `<a href="tel:${UI.esc(a.phone)}">${UI.esc(a.phone)}</a>`)}${kv("Email", a.email ? UI.esc(a.email) : "—")}
                    ${kv("Address", UI.esc(a.address), true)}${kv("State", UI.esc(a.state))}${kv("LGA", UI.esc(a.lga))}</div></div>
                <div class="dr-section"><h4>${a.account.type === "parent" ? "Parent / guardian account" : "Account"}</h4><div class="kv">
                    ${kv("Name", UI.esc(a.account.name))}${kv("Email", `<a href="mailto:${UI.esc(a.account.email)}">${UI.esc(a.account.email)}</a>`)}
                    ${kv("Phone", UI.esc(a.account.phone || "—"))}${kv("Type", a.account.type === "parent" ? "Parent" : "Self-applicant")}</div></div>
                <div class="dr-section"><h4>Education</h4><div class="kv">
                    ${kv("Qualification", UI.esc(a.qualification))}${kv("Graduation year", a.gradYear || "—")}${kv("Institution", UI.esc(a.institution), true)}
                    ${kv("WAEC/NECO", a.waecStatus === "Available" ? `${a.waecYear} · ${a.numAs} A's` : UI.esc(a.waecStatus))}
                    ${kv("Result document", a.waecFileUrl ? `<a href="${a.waecFileUrl}" target="_blank" rel="noopener"><i class="fa-regular fa-file-lines"></i> Open uploaded result</a>` : `<span class="muted">Not uploaded</span>`)}</div></div>
                <div class="dr-section"><h4>Payments</h4>${a.payments.length ? `<ul class="list">${a.payments.map((p) => `<li class="list-item"><span class="icon-tile ${p.status === "SUCCESS" ? "green" : p.status === "FAILED" ? "red" : ""}"><i class="fa-solid fa-naira-sign"></i></span><div class="grow"><strong>${PURPOSE[p.purpose] || p.purpose}${p.kind === "refund" ? " refund" : ""} · ${UI.naira(p.amount)}</strong><small class="mono">${UI.esc(p.ref)} · ${UI.dateTime(p.verifiedAt || p.createdAt)}</small></div>${UI.badge(p.status)}</li>`).join("")}</ul>` : `<p class="muted small">No payments yet.</p>`}</div>
                <div class="dr-section"><h4>Activity</h4><ul class="history">${[...a.history].reverse().map((h) => `<li class="${h.ok ? "ok" : ""}"><strong>${UI.esc(h.text)}</strong><small>${UI.dateTime(h.at)}</small></li>`).join("")}</ul></div>`,
            footer: `<button class="btn btn-ghost" id="adPrint" title="Print"><i class="fa-solid fa-print"></i></button>${acts.join("")}`
        });
        UI.$("#adPrint", d.el).onclick = () => UI.printHTML(`Application ${a.id}`, Applications.printHTML(a));
        UI.$$("[data-act]", d.el).forEach((b) => b.onclick = async () => {
            const act = b.dataset.act;
            try {
                if (act === "remind") {
                    const r = await API.post(`staff/applications/${enc(a.id)}/remind`);
                    UI.toast("Reminder sent", `${a.account.name} was reminded about the ${r.reminded} (portal + email).`, "success");
                    return;
                }
                if (act === "reject") {
                    const note = await askNote({ title: "Reject this application?", label: "Reason (sent to the applicant)", confirm: "Reject application", danger: true });
                    if (note === null) return;
                    await API.post(`staff/applications/${enc(a.id)}/reject`, { note });
                    UI.toast("Application rejected", a.name, "warning");
                } else {
                    const approve = act === "award-yes";
                    const note = await askNote({ title: approve ? "Approve the Excellence Award?" : "Decline the award?", label: "Note (optional, e.g. what you checked)", confirm: approve ? "Approve & admit" : "Decline & admit at full fee", danger: !approve });
                    if (note === null) return;
                    const r = await API.post(`staff/applications/${enc(a.id)}/award`, { approve, note });
                    UI.toast(approve ? "Award approved" : "Award declined", `${a.name} admitted — programme fee ${UI.naira(r.amountPayable)}.`, "success");
                }
                d.close(); onChange(); refreshCounts();
            } catch (e) { fail("Action failed")(e); }
        });
    }

    /** Small modal asking for an optional note. Resolves to the note, or null if cancelled. */
    function askNote({ title, label, confirm, danger }) {
        return new Promise((resolve) => {
            let done = false;
            const m = UI.modal({
                title, size: "sm", onClose: () => { if (!done) resolve(null); },
                body: `<div class="field"><label for="anNote">${label}</label><textarea id="anNote" class="textarea" maxlength="300" style="min-height:80px"></textarea></div>`,
                footer: `<button class="btn btn-ghost" data-close>Cancel</button><button class="btn ${danger ? "btn-danger" : "btn-primary"}" id="anOk">${confirm}</button>`
            });
            UI.$("#anOk", m.el).onclick = () => { done = true; resolve(UI.$("#anNote", m.el).value.trim()); m.close(); };
        });
    }

    async function refreshCounts() {
        try {
            const s = await API.get("staff/summary");
            const set = (id, n) => { const el = UI.$(`[data-count-for="${id}"]`); if (el) { el.textContent = n; el.hidden = !n; } };
            set("staff-scholarships", s.awardsToVerify);
            set("staff-payments", s.duplicates);
            return s;
        } catch (e) { return null; }
    }

    return { STATUSES, PURPOSE, lifecycle, openApplication, askNote, refreshCounts, fail };
})();

/* ---------------- Dashboard ---------------- */
Pages["staff-dashboard"] = async function (view, { session }) {
    view.innerHTML = `<div class="panel">${UI.skeleton(6)}</div>`;
    const s = await Staff.refreshCounts();
    if (!s) { view.innerHTML = UI.empty({ icon: "fa-plug-circle-xmark", title: "Couldn't load the dashboard", text: "Check your connection and reload." }); return; }
    const A = s.applications, hr = new Date().getHours();
    const kpi = (label, value, icon, tone, note, href) => `<a class="kpi" href="${href}" style="text-decoration:none"><div class="kpi-top"><p class="label">${label}</p><span class="icon-tile ${tone}"><i class="fa-solid ${icon}"></i></span></div><div class="value">${value}</div><span class="trend flat">${note}</span></a>`;
    let recent = [];
    try { recent = (await API.get("staff/applications")).results.slice(0, 6); } catch (e) { /* the tiles still help */ }
    view.innerHTML = `
        <div class="welcome"><div style="position:relative;z-index:1"><span class="badge badge-primary no-dot">${UI.dateLong(new Date())}</span><h2>${hr < 12 ? "Good morning" : hr < 17 ? "Good afternoon" : "Good evening"}, ${UI.esc(session.name.split(" ").slice(0, 2).join(" "))}</h2>
            <p>${UI.esc(s.intake || "No current intake")}: <b>${s.awardsToVerify}</b> Excellence Award${s.awardsToVerify === 1 ? "" : "s"} to verify${s.duplicates ? ` and <b>${s.duplicates}</b> duplicate payment${s.duplicates === 1 ? "" : "s"} to refund` : ""}.${s.cohortStart ? ` Classes begin <b>${UI.dateLong(Site.day(s.cohortStart))}</b>.` : ""}</p></div>
            <div class="actions"><a class="btn btn-primary" href="scholarships.html"><i class="fa-solid fa-award"></i> Verify awards</a><a class="btn btn-outline" href="applications.html"><i class="fa-solid fa-file-signature"></i> Applications</a></div></div>
        <div class="kpis">
            ${kpi("Applications", A.total || 0, "fa-file-signature", "", `${A.Pending || 0} awaiting application fee`, "applications.html")}
            ${kpi("Admitted", A.Admitted || 0, "fa-user-check", "cyan", "Programme fee not yet paid", "applications.html?status=Admitted")}
            ${kpi("Enrolled", s.enrolled, "fa-user-graduate", "green", "Programme fee paid", "applications.html?status=Enrolled")}
            ${kpi("Awards to verify", s.awardsToVerify, "fa-award", "gold", "Waiting for a school visit", "scholarships.html")}
            ${kpi("Collected", UI.naira(s.revenue.total), "fa-naira-sign", "grad", `${UI.naira(s.revenue.lastWeek)} in the last 7 days`, "payments.html")}
        </div>
        <div class="dash-grid cols-12">
            <div class="panel span-7"><div class="panel-head"><div><h3><i class="fa-solid fa-clock-rotate-left"></i>Latest applications</h3></div><a class="btn btn-sm btn-soft" href="applications.html">View all</a></div>
                ${recent.length ? `<ul class="list">${recent.map((a) => `<li class="list-item" style="cursor:pointer" data-app="${UI.esc(a.id)}">${UI.avatar(a.name, "sm")}<div class="grow"><strong>${UI.esc(a.name)}</strong><small>${UI.esc(a.programmeName)} · ${UI.timeAgo(a.createdAt)}${a.account.type === "parent" ? ` · via ${UI.esc(a.account.name)}` : ""}</small></div>${UI.badge(a.status)}</li>`).join("")}</ul>` : UI.empty({ icon: "fa-inbox", title: "No applications yet" })}</div>
            <div class="panel span-5"><div class="panel-head"><div><h3><i class="fa-solid fa-chair"></i>Seats taken</h3><p>Programme fee paid · ${UI.esc(s.intake || "")}</p></div></div><div class="panel-body">
                ${s.seats.length ? s.seats.map((r) => `<div class="mb-2"><div class="flex between small mb-1"><b>${UI.esc(r.programme)}</b><span class="muted">${r.taken} / ${r.capacity}</span></div><div class="progress ${r.taken / r.capacity > .85 ? "gold" : ""}"><span style="width:${Math.round(r.taken / r.capacity * 100)}%"></span></div></div>`).join("") : `<p class="muted small mb-0">No enrolments yet for this intake.</p>`}
                <div class="divider"></div>
                <div class="flex between small"><span class="muted">Application fees</span><b>${UI.naira(s.revenue.applicationFees)}</b></div>
                <div class="flex between small mt-1"><span class="muted">Programme fees</span><b>${UI.naira(s.revenue.programmeFees)}</b></div></div></div>
        </div>`;
    UI.$$("[data-app]", view).forEach((li) => li.onclick = () => Staff.openApplication(li.dataset.app, () => Pages["staff-dashboard"](view, { session })));
};

/* ---------------- Applications ---------------- */
Pages["staff-applications"] = function (view) {
    let status = UI.param("status") || "";
    view.innerHTML = `
        <div class="view-head"><div><h2>Applications</h2><p>Every application for every intake. Admission is automatic once the application fee is paid; Excellence Award requests wait for verification.</p></div>
            <div class="actions"><button class="btn btn-outline" id="appExport"><i class="fa-solid fa-file-csv"></i> Export CSV</button></div></div>
        <div class="stat-chips" id="statusChips" role="tablist" aria-label="Filter by status"></div>
        <div class="panel">
            <div class="table-tools">
                <div class="input-icon"><i class="fa-solid fa-magnifying-glass"></i><input class="input" id="aSearch" placeholder="Search name, number, email, phone…" aria-label="Search applications"></div>
                <select class="select" id="aProg" aria-label="Programme"><option value="">All programmes</option>${Programmes.all().map((p) => `<option value="${p.id}">${UI.esc(p.name)}</option>`).join("")}</select>
                <input type="date" class="input" id="aFrom" aria-label="From date" style="width:auto"><input type="date" class="input" id="aTo" aria-label="To date" style="width:auto">
                <button class="btn btn-ghost btn-sm" id="aClear"><i class="fa-solid fa-rotate-left"></i> Reset</button>
            </div>
            <div id="appTable">${UI.skeleton(6)}</div></div>`;
    let rows = [];
    const table = UI.dataTable("#appTable", {
        pageSize: 15, onRowClick: (id) => Staff.openApplication(id, load),
        empty: { icon: "fa-file-circle-question", title: "No applications found", text: "Nothing matches these filters yet." },
        columns: [
            { key: "id", label: "Application", render: (a) => `<span class="ref">${UI.esc(a.id)}</span>` },
            { key: "name", label: "Applicant", render: (a) => `<div class="person">${UI.avatar(a.name, "sm")}<div><strong>${UI.esc(a.name)}</strong><small>${a.account.type === "parent" ? `Parent: ${UI.esc(a.account.name)}` : UI.esc(a.account.email)}</small></div></div>` },
            { key: "programmeName", label: "Programme", render: (a) => `<span class="small">${UI.esc(a.programmeName)}</span>` },
            { key: "createdAt", label: "Applied", render: (a) => `<span class="small">${UI.date(a.createdAt)}</span>` },
            { key: "applicationFeePaidAt", label: "App. fee", sortValue: (a) => a.applicationFeePaidAt || "", render: (a) => UI.badge(a.applicationFeePaidAt ? "Paid" : "Unpaid") },
            { key: "award", label: "Award", sortValue: (a) => a.award?.status || "", render: (a) => a.award ? UI.badge(a.award.status) : `<span class="muted small">—</span>` },
            { key: "status", label: "Status", render: (a) => UI.badge(a.status) }
        ],
        mobile: (a) => `<div class="m-row"><strong>${UI.esc(a.name)}</strong>${UI.badge(a.status)}</div><div class="m-row"><span class="ref">${UI.esc(a.id)}</span><span class="small">${UI.date(a.createdAt)}</span></div><div class="m-row"><span>${UI.esc(a.programmeName)}</span></div>`
    });
    let counts = {};
    function chips() {
        UI.$("#statusChips").innerHTML = [["", "All", counts.all || 0], ...Staff.STATUSES.map((s) => [s, s, counts[s] || 0])]
            .map(([v, l, n]) => `<button class="stat-chip ${status === v ? "active" : ""}" data-st="${v}" role="tab" aria-selected="${status === v}">${l} <b>${n}</b></button>`).join("");
        UI.$$("#statusChips .stat-chip").forEach((c) => c.onclick = () => { status = c.dataset.st; load(); });
    }
    async function load() {
        try {
            const r = await API.get("staff/applications", { status, q: UI.$("#aSearch").value.trim(), programme: UI.$("#aProg").value, from: UI.$("#aFrom").value, to: UI.$("#aTo").value });
            rows = r.results; counts = r.counts;
            table.update(rows, { resetPage: false });
            chips();
        } catch (e) { Staff.fail("Couldn't load applications")(e); }
    }
    UI.$("#aSearch").addEventListener("input", UI.debounce(load, 250));
    ["#aProg", "#aFrom", "#aTo"].forEach((s) => UI.$(s).addEventListener("change", load));
    UI.$("#aClear").onclick = () => { ["#aSearch", "#aProg", "#aFrom", "#aTo"].forEach((s) => UI.$(s).value = ""); status = ""; load(); };
    UI.$("#appExport").onclick = () => UI.downloadCSV("tsce-applications.csv", rows.map((a) => ({
        Application: a.id, Applicant: a.name, Phone: a.phone, Email: a.email, Account: a.account.email, AccountType: a.account.type,
        Programme: a.programmeName, Intake: a.intake, Applied: UI.date(a.createdAt), ApplicationFee: a.applicationFeePaidAt ? "Paid" : "Unpaid",
        Award: a.award?.status || "", Status: a.status, ProgrammeFee: a.amountPayable, ProgrammeFeeStatus: a.paymentStatus
    })));
    load();
    const open = UI.param("id"); if (open) Staff.openApplication(open, load);
};

/* ---------------- Excellence Awards (verification queue) ---------------- */
Pages["staff-scholarships"] = function (view) {
    let tab = "Pending";
    const pct = Site.settings?.discounts?.excellence || 50;
    const rule = `WAEC/NECO ${Site.settings?.discounts?.excellenceMinYear || 2020}–date with ${Site.settings?.discounts?.excellenceMinAs || 5}+ A's`;
    view.innerHTML = `
        <div class="view-head"><div><h2>Excellence Awards</h2><p>Applicants who requested the ${pct}% award bring their original result to TSCE. Verify it here — either decision admits them.</p></div></div>
        <div class="alert mb-3"><i class="fa-solid fa-circle-info"></i><p><b>How to verify:</b> check the original certificate or scratch-card result against ${rule}, then approve (${pct}% off the programme fee) or decline (normal fee). Applicants who haven't paid the application fee yet don't appear in the queue.</p></div>
        <div class="panel"><div class="panel-head"><div class="tabs" id="awTabs" role="tablist"></div>
            <div class="input-icon" style="width:260px;max-width:100%"><i class="fa-solid fa-magnifying-glass"></i><input class="input" id="awSearch" placeholder="Search…" aria-label="Search awards" style="height:40px"></div></div>
            <div id="awTable">${UI.skeleton(5)}</div></div>`;
    const table = UI.dataTable("#awTable", {
        pageSize: 15, onRowClick: (id) => Staff.openApplication(id, load),
        empty: { icon: "fa-award", title: "Nothing here", text: tab === "Pending" ? "No awards are waiting for verification." : "No awards in this list." },
        columns: [
            { key: "name", label: "Applicant", render: (a) => `<div class="person">${UI.avatar(a.name, "sm")}<div><strong>${UI.esc(a.name)}</strong><small>${UI.esc(a.id)}</small></div></div>` },
            { key: "programmeName", label: "Programme", render: (a) => `<span class="small">${UI.esc(a.programmeName)}</span>` },
            { key: "evidence", label: "Declared result", sortable: false, render: (a) => `<span class="small">${UI.esc(a.award.evidence || "")}</span>` },
            { key: "account", label: "Contact", sortable: false, render: (a) => `<span class="small">${UI.esc(a.account.name)}<br><a href="tel:${UI.esc(a.account.phone || a.phone)}">${UI.esc(a.account.phone || a.phone)}</a></span>` },
            { key: "status", label: "Status", render: (a) => a.award.status === "Pending" ? (a.status === "Awaiting Verification" ? UI.badge("Awaiting Verification") : `<span class="small muted">App. fee unpaid</span>`) : UI.badge(a.award.status) },
            { key: "", label: "", sortable: false, render: (a) => a.status === "Awaiting Verification" ? `<button class="btn btn-xs btn-primary">Verify</button>` : "" }
        ]
    });
    let all = [];
    function render() {
        const q = UI.$("#awSearch").value.toLowerCase();
        const list = all.filter((a) => (tab === "All" || a.award.status === tab) && [a.name, a.id, a.account.name, a.account.email].join(" ").toLowerCase().includes(q));
        if (tab === "Pending") list.sort((a, b) => (b.status === "Awaiting Verification") - (a.status === "Awaiting Verification"));
        table.update(list);
        const n = (s) => all.filter((a) => s === "All" || a.award.status === s).length;
        UI.$("#awTabs").innerHTML = ["Pending", "Approved", "Rejected", "All"].map((t) => `<button class="tab ${t === tab ? "active" : ""}" data-tab="${t}" role="tab">${t === "Pending" ? "To verify" : t} (${n(t)})</button>`).join("");
        UI.$$("#awTabs .tab").forEach((b) => b.onclick = () => { tab = b.dataset.tab; render(); });
    }
    async function load() {
        try { all = (await API.get("staff/applications", { award: "any" })).results; render(); }
        catch (e) { Staff.fail("Couldn't load awards")(e); }
    }
    UI.$("#awSearch").addEventListener("input", UI.debounce(render, 150));
    load();
};

/* ---------------- Payments ---------------- */
Pages["staff-payments"] = function (view) {
    view.innerHTML = `
        <div class="view-head"><div><h2>Payments</h2><p>Every Zainpay transaction — application fees, programme fees and recorded refunds.</p></div>
            <div class="actions"><button class="btn btn-outline" id="expPay"><i class="fa-solid fa-file-csv"></i> Export CSV</button></div></div>
        <div class="kpis" id="payKpis"></div>
        <div class="panel">
            <div class="table-tools"><div class="input-icon"><i class="fa-solid fa-magnifying-glass"></i><input class="input" id="tSearch" placeholder="Search name, reference, application…" aria-label="Search transactions"></div>
                <select class="select" id="tStatus" aria-label="Status"><option value="">All statuses</option><option>SUCCESS</option><option>PENDING</option><option>FAILED</option><option>REFUNDED</option></select>
                <select class="select" id="tPurpose" aria-label="Fee"><option value="">Both fees</option><option value="application_fee">Application fee</option><option value="programme_fee">Programme fee</option></select>
                <label class="check small"><input type="checkbox" id="tDup"> Duplicates only</label></div>
            <div id="payTable">${UI.skeleton(6)}</div></div>`;
    UI.$("#tStatus").value = UI.param("status") || "";
    let rows = [];
    const table = UI.dataTable("#payTable", {
        pageSize: 15, rowId: (p) => p.ref, onRowClick: (ref) => detail(rows.find((p) => p.ref === ref)),
        empty: { icon: "fa-receipt", title: "No transactions", text: "Nothing matches these filters yet." },
        columns: [
            { key: "ref", label: "Reference", render: (p) => `<span class="ref">${UI.esc(p.ref)}</span>${p.isDuplicate ? ` <span class="badge badge-danger no-dot">Duplicate</span>` : ""}` },
            { key: "name", label: "Applicant", render: (p) => `<div class="person">${UI.avatar(p.name, "sm")}<div><strong>${UI.esc(p.name)}</strong><small class="mono">${UI.esc(p.applicationId || "")}</small></div></div>` },
            { key: "purpose", label: "For", render: (p) => `<span class="small">${Staff.PURPOSE[p.purpose] || "—"}${p.kind === "refund" ? " · refund" : ""}</span>` },
            { key: "amount", label: "Amount", cls: "num", render: (p) => `<b>${p.kind === "refund" ? "−" : ""}${UI.naira(p.amount)}</b>` },
            { key: "status", label: "Status", render: (p) => UI.badge(p.status) },
            { key: "createdAt", label: "Date", render: (p) => `<span class="small">${UI.dateTime(p.verifiedAt || p.createdAt)}</span>` }
        ],
        mobile: (p) => `<div class="m-row"><strong>${UI.esc(p.name)}</strong>${UI.badge(p.status)}</div><div class="m-row"><span class="ref">${UI.esc(p.ref)}</span><b>${UI.naira(p.amount)}</b></div>`
    });
    function kpis(s) {
        UI.$("#payKpis").innerHTML = [
            ["Collected", UI.naira(s.collected), "fa-naira-sign", "grad", "All successful payments"],
            ["Application fees", UI.naira(s.applicationFees), "fa-file-invoice", "", "Non-refundable"],
            ["Programme fees", UI.naira(s.programmeFees), "fa-graduation-cap", "green", "Seats secured"],
            ["Pending / failed", `${s.pending} / ${s.failed}`, "fa-hourglass-half", "gold", "Checked automatically every 5 min"],
            ["Duplicates to refund", s.duplicates, "fa-rotate-left", s.duplicates ? "red" : "cyan", `${UI.naira(s.refunded)} refunded so far`]
        ].map(([l, v, i, c, n]) => `<div class="kpi"><div class="kpi-top"><p class="label">${l}</p><span class="icon-tile ${c}"><i class="fa-solid ${i}"></i></span></div><div class="value">${v}</div><span class="trend flat">${n}</span></div>`).join("");
    }
    async function load() {
        try {
            const r = await API.get("staff/payments", { status: UI.$("#tStatus").value, purpose: UI.$("#tPurpose").value, q: UI.$("#tSearch").value.trim() });
            rows = UI.$("#tDup").checked ? r.results.filter((p) => p.isDuplicate) : r.results;
            table.update(rows, { resetPage: false });
            kpis(r.summary);
        } catch (e) { Staff.fail("Couldn't load payments")(e); }
    }
    function detail(p) {
        if (!p) return;
        const acts = [];
        if (["PENDING", "FAILED"].includes(p.status) && p.kind === "charge") acts.push(`<button class="btn btn-outline" id="pCheck"><i class="fa-solid fa-rotate"></i> Check with Zainpay</button>`);
        if (p.isDuplicate) acts.push(`<button class="btn btn-soft-danger" id="pRefund"><i class="fa-solid fa-rotate-left"></i> Record refund</button>`);
        if (["SUCCESS", "REFUNDED"].includes(p.status)) acts.push(`<button class="btn btn-primary" id="pReceipt"><i class="fa-solid fa-receipt"></i> Receipt</button>`);
        const kv = (k, v, full) => `<div class="${full ? "full" : ""}"><small>${k}</small><strong>${v}</strong></div>`;
        const d = UI.drawer({
            title: `${p.kind === "refund" ? "Refund" : "Payment"} ${UI.badge(p.status)}`, subtitle: `<span class="mono">${UI.esc(p.ref)}</span>`,
            body: `${p.isDuplicate ? `<div class="alert danger mb-2"><i class="fa-solid fa-triangle-exclamation"></i><p><b>Duplicate payment.</b> This fee was already paid by an earlier transaction. Send the money back by bank transfer, then record the refund here.</p></div>` : ""}
                <div class="dr-section"><div class="kv">
                ${kv("Amount", `<span style="font-size:1.3rem;font-family:var(--font-head)">${UI.naira(p.amount)}</span>`)}${kv("For", Staff.PURPOSE[p.purpose] || "—")}
                ${kv("Applicant", UI.esc(p.name))}${kv("Account email", UI.esc(p.email || "—"))}
                ${kv("Application", p.applicationId ? `<a href="applications.html?id=${encodeURIComponent(p.applicationId)}" class="mono">${UI.esc(p.applicationId)}</a>` : "—")}${kv("Student", UI.esc(p.studentId || "—"))}
                ${kv("Gateway", p.gateway === "manual" ? "Manual (bank transfer)" : `Zainpay${p.channel ? " · " + UI.esc(Payments.CHANNEL[p.channel] || p.channel) : ""}`)}${kv("Created", UI.dateTime(p.createdAt))}
                ${p.verifiedAt ? kv("Confirmed", UI.dateTime(p.verifiedAt)) : ""}${p.refundOf ? kv("Refund of", `<span class="mono">${UI.esc(p.refundOf)}</span>`) : ""}
                ${p.failureReason ? kv("Failure reason", `<span style="color:var(--danger)">${UI.esc(p.failureReason)}</span>`, true) : ""}
                ${kv("Description", UI.esc(p.description || ""), true)}</div></div>`,
            footer: acts.join("") || `<button class="btn btn-ghost" data-close>Close</button>`
        });
        UI.$("#pReceipt", d.el)?.addEventListener("click", () => Payments.showReceipt(p));
        UI.$("#pCheck", d.el)?.addEventListener("click", async (e) => {
            e.target.disabled = true;
            try { const r = await API.post(`payments/${encodeURIComponent(p.ref)}/check`); UI.toast("Checked with Zainpay", `Status: ${r.status}`, r.status === "SUCCESS" ? "success" : "info"); d.close(); load(); }
            catch (err) { e.target.disabled = false; Staff.fail("Couldn't check")(err); }
        });
        UI.$("#pRefund", d.el)?.addEventListener("click", () => {
            const m = UI.modal({
                title: "Record refund", subtitle: `${UI.naira(p.amount)} to ${UI.esc(p.name)}`, size: "sm",
                body: `<p class="small muted">Send the money back by bank transfer first, then record it here. The account holder is notified by email.</p>
                    <form id="rfForm" novalidate><div class="field mb-2"><label for="rfRef">Bank transfer reference <span class="req">*</span></label><input id="rfRef" class="input" required maxlength="100"></div>
                    <div class="field"><label for="rfNote">Note</label><input id="rfNote" class="input" maxlength="300" placeholder="e.g. Paid twice from two tabs"></div></form>`,
                footer: `<button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-danger" id="rfSave">Record refund</button>`
            });
            UI.$("#rfSave", m.el).onclick = async () => {
                if (!UI.validate(UI.$("#rfForm", m.el))) return;
                try {
                    await API.post(`staff/payments/${encodeURIComponent(p.ref)}/refund`, { transferRef: UI.$("#rfRef", m.el).value.trim(), note: UI.$("#rfNote", m.el).value.trim() });
                    m.close(); d.close(); UI.toast("Refund recorded", `${UI.naira(p.amount)} — ${p.name}`, "success"); load(); Staff.refreshCounts();
                } catch (e) { Staff.fail("Couldn't record refund")(e); }
            };
        });
    }
    UI.$("#tSearch").addEventListener("input", UI.debounce(load, 250));
    ["#tStatus", "#tPurpose", "#tDup"].forEach((s) => UI.$(s).addEventListener("change", load));
    UI.$("#expPay").onclick = () => UI.downloadCSV("tsce-payments.csv", rows.map((p) => ({
        Reference: p.ref, Kind: p.kind, For: Staff.PURPOSE[p.purpose] || "", Applicant: p.name, Account: p.email, Application: p.applicationId || "",
        Amount: (p.kind === "refund" ? -1 : 1) * p.amount, Status: p.status, Duplicate: p.isDuplicate ? "yes" : "", Created: UI.dateTime(p.createdAt), Confirmed: p.verifiedAt ? UI.dateTime(p.verifiedAt) : ""
    })));
    load();
    const ref = UI.param("ref");
    if (ref) API.get(`payments/${encodeURIComponent(ref)}`).then(detail).catch(() => { });
};

/* ---------------- Staff accounts (admin) ---------------- */
Pages["staff-staff"] = function (view) {
    const DEPTS = ["Management", "Admissions", "Finance", "Academics"];
    const ACCESS = { none: "No login (e.g. instructor)", staff: "Staff portal", admin: "Admin (staff + settings)" };
    const me = Auth.current();
    view.innerHTML = `<div class="view-head"><div><h2>Staff</h2><p>Staff records and portal access. Instructors can be listed without a login.</p></div><div class="actions"><button class="btn btn-primary" id="addStaff"><i class="fa-solid fa-user-plus"></i> Add staff</button></div></div>
        <div class="panel"><div class="table-tools"><div class="input-icon"><i class="fa-solid fa-magnifying-glass"></i><input class="input" id="sfQ" placeholder="Search staff…" aria-label="Search staff"></div>
            <select class="select" id="sfD" aria-label="Department"><option value="">All departments</option>${DEPTS.map((d) => `<option>${d}</option>`).join("")}</select></div><div id="sfT">${UI.skeleton(5)}</div></div>`;
    let all = [];
    const table = UI.dataTable("#sfT", {
        pageSize: 20, onRowClick: (id) => edit(all.find((s) => String(s.id) === id)),
        columns: [
            { key: "fullName", label: "Name", render: (s) => `<div class="person">${UI.avatar(s.fullName, "sm")}<div><strong>${UI.esc(s.fullName)}</strong><small>${UI.esc(s.email || "no email")}</small></div></div>` },
            { key: "staffNo", label: "No.", render: (s) => `<span class="ref">${UI.esc(s.staffNo)}</span>` },
            { key: "title", label: "Role" }, { key: "department", label: "Department", render: (s) => `<span class="badge badge-neutral no-dot">${UI.esc(s.department)}</span>` },
            { key: "access", label: "Portal access", render: (s) => s.access === "none" ? `<span class="muted small">No login</span>` : `<span class="badge ${s.access === "admin" ? "badge-dark" : "badge-primary"} no-dot">${s.access}</span>` },
            { key: "status", label: "Status", render: (s) => UI.badge(s.status) },
            { key: "lastLogin", label: "Last sign-in", render: (s) => `<span class="small">${s.lastLogin ? UI.timeAgo(s.lastLogin) : "—"}</span>` }
        ]
    });
    function render() {
        const q = UI.$("#sfQ").value.toLowerCase(), d = UI.$("#sfD").value;
        table.update(all.filter((s) => (!d || s.department === d) && [s.fullName, s.title, s.email, s.staffNo].join(" ").toLowerCase().includes(q)), { resetPage: false });
    }
    async function load() { try { all = await API.get("staff/staff"); render(); } catch (e) { Staff.fail("Couldn't load staff")(e); } }
    function showPassword(name, email, password) {
        UI.modal({
            title: "Temporary password", size: "sm",
            body: `<p>Give this to <b>${UI.esc(name)}</b> (${UI.esc(email)}). They'll be asked to choose their own password when they first sign in.</p>
                <div class="bank-box"><div class="row"><span class="muted">Password</span><span><strong class="mono" style="font-size:1.1rem">${UI.esc(password)}</strong><button class="copy-btn" id="cpTemp">Copy</button></span></div></div>
                <p class="small muted mt-2">It won't be shown again. If it's lost, use "Reset password".</p>`,
            footer: `<button class="btn btn-primary" data-close>Done</button>`,
            onOpen: (m) => { UI.$("#cpTemp", m.el).onclick = () => UI.copy(password); }
        });
    }
    function form(s = {}) {
        return `<form id="stf" class="form-grid" novalidate>
            <div class="field"><label for="st_n">Full name <span class="req">*</span></label><input id="st_n" name="fullName" class="input" required value="${UI.esc(s.fullName || "")}"></div>
            <div class="field"><label for="st_t">Job title <span class="req">*</span></label><input id="st_t" name="title" class="input" required value="${UI.esc(s.title || "")}" placeholder="e.g. Instructor — Networking"></div>
            <div class="field"><label for="st_e">Email</label><input id="st_e" name="email" type="email" class="input" value="${UI.esc(s.email || "")}" ${s.userId ? "readonly" : ""}><span class="hint">${s.userId ? "This is their sign-in email." : "Needed for portal access."}</span></div>
            <div class="field"><label for="st_p">Phone</label><input id="st_p" name="phone" class="input" data-type="phone" value="${UI.esc(s.phone || "")}"></div>
            <div class="field"><label for="st_d">Department</label><select id="st_d" name="department" class="select">${DEPTS.map((d) => `<option ${s.department === d ? "selected" : ""}>${d}</option>`).join("")}</select></div>
            <div class="field"><label for="st_a">Portal access</label><select id="st_a" name="access" class="select">${Object.entries(ACCESS).map(([v, l]) => `<option value="${v}" ${(s.access || "staff") === v ? "selected" : ""}>${l}</option>`).join("")}</select></div>
            ${s.id ? `<div class="field"><label for="st_s">Status</label><select id="st_s" name="status" class="select">${["Active", "On Leave", "Inactive"].map((x) => `<option ${s.status === x ? "selected" : ""}>${x}</option>`).join("")}</select><span class="hint">On leave or inactive staff can't sign in.</span></div>` : ""}
        </form>`;
    }
    function edit(s) {
        const isNew = !s, self = s && s.userId === me.id;
        const m = UI.modal({
            title: isNew ? "Add staff member" : `Edit ${UI.esc(s.fullName)}`, subtitle: isNew ? "" : `<span class="mono">${UI.esc(s.staffNo)}</span>`, size: "lg",
            body: form(s || {}) + (self ? `<p class="hint mt-2">You can't change your own access or status.</p>` : ""),
            footer: `${!isNew && s.userId && s.access !== "none" && !self ? `<button class="btn btn-ghost" id="stReset" style="margin-right:auto"><i class="fa-solid fa-key"></i> Reset password</button>` : ""}<button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-primary" id="stSave">${isNew ? "Add staff" : "Save changes"}</button>`
        });
        const f = UI.$("#stf", m.el);
        if (self) UI.$$("#st_a, #st_s", m.el).forEach((x) => x.disabled = true);
        UI.liveValidate(f);
        UI.$("#stSave", m.el).onclick = async () => {
            if (!UI.validate(f)) return;
            const d = UI.formData(f);
            if (self) { delete d.access; delete d.status; }
            try {
                const r = isNew ? await API.post("staff/staff", d) : await API.patch(`staff/staff/${s.id}`, d);
                m.close(); UI.toast(isNew ? "Staff added" : "Staff updated", r.staff.fullName, "success"); load();
                if (r.temporaryPassword) showPassword(r.staff.fullName, r.staff.email, r.temporaryPassword);
            } catch (e) { if (!API.showFieldErrors(f, e)) Staff.fail("Couldn't save")(e); }
        };
        UI.$("#stReset", m.el)?.addEventListener("click", async () => {
            if (!(await UI.confirm({ title: "Reset password?", message: `${UI.esc(s.fullName)} gets a temporary password and must choose a new one at next sign-in.`, confirmText: "Reset password", icon: "fa-key" }))) return;
            try { const r = await API.post(`staff/users/${s.userId}/reset-password`); m.close(); showPassword(s.fullName, r.email, r.temporaryPassword); }
            catch (e) { Staff.fail("Couldn't reset")(e); }
        });
    }
    UI.$("#addStaff").onclick = () => edit(null);
    UI.$("#sfQ").oninput = UI.debounce(render, 150); UI.$("#sfD").onchange = render;
    load();
};

/* ---------------- Settings (admin) ---------------- */
Pages["staff-settings"] = async function (view) {
    view.innerHTML = `<div class="panel">${UI.skeleton(8)}</div>`;
    let s;
    try { s = await API.get("staff/settings"); } catch (e) { view.innerHTML = UI.empty({ icon: "fa-gear", title: "Couldn't load settings", text: UI.esc(e.message) }); return; }
    const sw = (sec, k, v, l, d) => `<div class="setting-row"><div><strong>${l}</strong><small>${d}</small></div><label class="switch"><input type="checkbox" name="${k}" ${v ? "checked" : ""} aria-label="${l}"><span></span></label></div>`;
    const f = (id, name, label, value, type = "text", extra = "") => `<div class="field ${extra}"><label for="${id}">${label}</label><input id="${id}" name="${name}" type="${type}" class="input" value="${UI.esc(value ?? "")}"></div>`;
    const g = s.gateway, inst = s.institution, adm = s.admissions, disc = s.discounts, nt = s.notifications;
    view.innerHTML = `<div class="view-head"><div><h2>Settings</h2><p>Institution profile, admissions calendar, fees, discounts and notifications.</p></div></div>
        <div class="settings-layout">
            <nav class="panel settings-nav" aria-label="Settings sections">${[["inst", "fa-building-columns", "Institution"], ["adm", "fa-door-open", "Admissions"], ["disc", "fa-percent", "Discounts"], ["notif", "fa-bell", "Notifications"], ["pay", "fa-credit-card", "Payments & email"]].map(([id, i, t], k) => `<a href="#${id}" class="${k === 0 ? "active" : ""}"><i class="fa-solid ${i}"></i>${t}</a>`).join("")}</nav>
            <div style="display:grid;gap:20px">
                <form class="panel" id="inst" data-sec="institution" novalidate><div class="panel-head"><div><h3><i class="fa-solid fa-building-columns"></i>Institution</h3><p>Shown on receipts, certificates and the website</p></div></div><div class="panel-body"><div class="form-grid">
                    ${f("i_n", "name", "Name", inst.name, "text", "span-2")}${f("i_s", "short", "Short name", inst.short)}${f("i_c", "city", "City", inst.city)}
                    ${f("i_a", "address", "Address", inst.address, "text", "span-2")}${f("i_p", "phones", "Phone numbers (comma-separated)", (inst.phones || []).join(", "), "text", "span-2")}
                    ${f("i_e", "email", "Email", inst.email, "email")}${f("i_w", "website", "Website", inst.website)}
                    ${f("i_dn", "directorName", "Director's name (signs certificates)", inst.directorName)}${f("i_dt", "directorTitle", "Director's title", inst.directorTitle)}
                </div></div><div class="table-foot"><span></span><button class="btn btn-primary">Save</button></div></form>
                <form class="panel" id="adm" data-sec="admissions" novalidate><div class="panel-head"><div><h3><i class="fa-solid fa-door-open"></i>Admissions</h3><p>Current intake, application window and application fee</p></div><button type="button" class="btn btn-sm btn-outline" id="newIntake"><i class="fa-solid fa-plus"></i> Start new intake</button></div><div class="panel-body"><div class="form-grid">
                    ${f("a_i", "intake", "Current intake name", adm.intake, "text", "span-2")}
                    ${f("a_o", "opens", "Applications open", adm.opens, "date")}${f("a_c", "closes", "Applications close", adm.closes, "date")}
                    ${f("a_d", "cohortDate", "Classes start", adm.cohortDate, "date")}${f("a_e", "earlyBirdDeadline", "Early bird: programme fee paid before", adm.earlyBirdDeadline, "date")}
                    ${f("a_f", "applicationFee", "Application fee (₦)", adm.applicationFee, "number")}
                    <div class="span-2">${sw("admissions", "acceptingApplications", adm.acceptingApplications, "Accept new applications", "Turn off to close the application form immediately")}</div>
                </div></div><div class="table-foot"><span class="small muted">Changes apply to new applications and payments from now on.</span><button class="btn btn-primary">Save</button></div></form>
                <form class="panel" id="disc" data-sec="discounts" novalidate><div class="panel-head"><div><h3><i class="fa-solid fa-percent"></i>Discounts</h3><p>Programme-fee discounts — they don't stack; the better one applies</p></div></div><div class="panel-body"><div class="form-grid">
                    ${f("d_e", "earlyBirdPct", "Early bird (%)", disc.earlyBirdPct, "number")}${f("d_x", "excellencePct", "Excellence Award (%)", disc.excellencePct, "number")}
                    ${f("d_y", "excellenceMinYear", "Excellence: WAEC/NECO from year", disc.excellenceMinYear, "number")}${f("d_a", "excellenceMinAs", "Excellence: minimum A's", disc.excellenceMinAs, "number")}
                </div></div><div class="table-foot"><span></span><button class="btn btn-primary">Save</button></div></form>
                <form class="panel" id="notif" data-sec="notifications" novalidate><div class="panel-head"><div><h3><i class="fa-solid fa-bell"></i>Notifications</h3></div></div><div class="panel-body">
                    ${sw("notifications", "emailNotifications", nt.emailNotifications, "Email applicants and parents", "Admission, payment and award updates (also shown in the portal)")}
                    ${sw("notifications", "staffPaymentAlerts", nt.staffPaymentAlerts, "Staff payment alerts", "Notify staff of every programme-fee payment")}
                    ${sw("notifications", "staffApplicationAlerts", nt.staffApplicationAlerts, "Staff application alerts", "Notify staff of every new application")}
                </div><div class="table-foot"><span></span><button class="btn btn-primary">Save</button></div></form>
                <div class="panel" id="pay"><div class="panel-head"><div><h3><i class="fa-solid fa-credit-card"></i>Payments & email</h3><p>Configured on the server (backend/.env) — shown here for reference</p></div><span class="badge ${g.name === "zainpay" && g.environment === "live" ? "badge-success" : "badge-warning"}">${g.name === "simulator" ? "Simulator" : `Zainpay · ${UI.esc(g.environment)}`}</span></div><div class="panel-body"><div class="kv">
                    <div><small>Gateway</small><strong>${g.name === "simulator" ? "Built-in simulator (no real money)" : "Zainpay"}</strong></div>
                    <div><small>Payment channels</small><strong>${g.channels.length ? UI.esc(g.channels.join(", ").replace("bank_transfer", "Bank transfer")) : "All channels"}</strong></div>
                    <div><small>Transaction charge (paid by payer)</small><strong>${UI.naira(g.payerCharge)}</strong></div>
                    <div><small>Reference prefix</small><strong class="mono">${UI.esc(g.refPrefix)}</strong></div>
                    <div class="full"><small>Outgoing email</small><strong>${g.emailConfigured ? "Configured (Gmail SMTP)" : `<span style="color:var(--danger)">Not configured — emails are not being sent</span>`}</strong></div>
                </div></div></div>
            </div></div>`;

    function payload(form) {
        const d = UI.formData(form);
        UI.$$('input[type="checkbox"]', form).forEach((c) => d[c.name] = c.checked);
        UI.$$('input[type="number"]', form).forEach((n) => d[n.name] = n.value === "" ? null : +n.value);
        UI.$$('input[type="date"]', form).forEach((n) => d[n.name] = n.value || null);
        if (form.dataset.sec === "institution") d.phones = d.phones.split(",").map((x) => x.trim()).filter(Boolean);
        return d;
    }
    UI.$$("form[data-sec]", view).forEach((form) => form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const btn = UI.$("button.btn-primary", form);
        btn.disabled = true;
        try {
            await API.patch("staff/settings", { [form.dataset.sec]: payload(form) });
            UI.toast("Settings saved", "", "success", 2500);
            await Site.load();
        } catch (err) { if (!API.showFieldErrors(form, err)) Staff.fail("Couldn't save")(err); }
        finally { btn.disabled = false; }
    }));
    UI.$$(".settings-nav a", view).forEach((a) => a.onclick = (e) => { e.preventDefault(); UI.$$(".settings-nav a").forEach((x) => x.classList.toggle("active", x === a)); UI.$(a.getAttribute("href")).scrollIntoView({ behavior: "smooth", block: "start" }); });
    UI.$("#newIntake").onclick = () => {
        const m = UI.modal({
            title: "Start a new intake", subtitle: "New applications go to the new intake. Existing applications keep theirs.", size: "lg",
            body: `<form id="niForm" class="form-grid" novalidate>
                <div class="field span-2"><label for="ni_n">Intake name <span class="req">*</span></label><input id="ni_n" name="intake" class="input" required placeholder="e.g. January 2027 Cohort"></div>
                <div class="field"><label for="ni_o">Applications open</label><input id="ni_o" name="opens" type="date" class="input"></div>
                <div class="field"><label for="ni_c">Applications close</label><input id="ni_c" name="closes" type="date" class="input"></div>
                <div class="field"><label for="ni_d">Classes start <span class="req">*</span></label><input id="ni_d" name="cohortDate" type="date" class="input" required></div>
                <div class="field"><label for="ni_e">Early bird: paid before</label><input id="ni_e" name="earlyBirdDeadline" type="date" class="input"></div></form>`,
            footer: `<button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-primary" id="niSave">Start intake</button>`
        });
        UI.$("#niSave", m.el).onclick = async () => {
            const form = UI.$("#niForm", m.el);
            if (!UI.validate(form)) return;
            const d = UI.formData(form);
            ["opens", "closes", "earlyBirdDeadline"].forEach((k) => d[k] = d[k] || null);
            try { await API.post("staff/intakes", d); m.close(); UI.toast("New intake started", d.intake, "success"); await Site.load(); Pages["staff-settings"](view); }
            catch (err) { if (!API.showFieldErrors(form, err)) Staff.fail("Couldn't start intake")(err); }
        };
    };
};
