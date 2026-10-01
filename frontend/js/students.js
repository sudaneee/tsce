/* ==========================================================================
   TSCE — Students: portal pages, attendance, assessments, certificates
   ========================================================================== */

const Students = (() => {
    const all = () => DB.all("students");
    const get = (id) => DB.get("students", id);
    const fullName = (s) => [s.firstName, s.middleName, s.lastName].filter(Boolean).join(" ");
    const grade = (sc) => sc >= 80 ? "A" : sc >= 70 ? "B" : sc >= 60 ? "C" : sc >= 50 ? "D" : "F";
    const gradeTone = (g) => ({ A: "success", B: "primary", C: "info", D: "warning", F: "danger" }[g] || "neutral");

    function attendance(id) {
        const recs = DB.where("attendance", (a) => a.studentId === id).sort((a, b) => new Date(a.date) - new Date(b.date));
        const present = recs.filter((r) => r.status === "Present").length, late = recs.filter((r) => r.status === "Late").length, absent = recs.filter((r) => r.status === "Absent").length;
        return { recs, total: recs.length, present, late, absent, rate: recs.length ? Math.round((present + late) / recs.length * 100) : 0 };
    }
    function results(id) {
        const recs = DB.where("results", (r) => r.studentId === id && r.status === "Published").sort((a, b) => new Date(a.date) - new Date(b.date));
        const avg = recs.length ? Math.round(recs.reduce((t, r) => t + r.score, 0) / recs.length) : 0;
        return { recs, avg, grade: recs.length ? grade(avg) : "—", best: recs.reduce((m, r) => r.score > (m?.score || 0) ? r : m, null) };
    }
    function modules(s) {
        const p = Programmes.get(s.programmeId);
        return p.modules.map((m, i) => ({ name: m, pct: s.moduleProgress?.[i] ?? 0, index: i }));
    }
    function eligibility(s) {
        const att = attendance(s.id), res = results(s.id);
        const checks = [
            { label: "All modules completed", ok: s.progress >= 100, value: `${s.progress}%` },
            { label: "Attendance of at least 75%", ok: att.total === 0 ? false : att.rate >= 75, value: `${att.rate}%` },
            { label: "Assessment average of 50% or more", ok: res.avg >= 50, value: res.recs.length ? `${res.avg}%` : "—" },
            { label: "Programme fees fully paid", ok: s.paymentStatus === "Paid", value: s.paymentStatus }
        ];
        return { checks, eligible: checks.every((c) => c.ok) };
    }
    function certState(s) {
        if (s.certificateStatus === "Issued") return "Issued";
        if (s.certificateStatus === "Revoked") return "Revoked";
        return eligibility(s).eligible ? "Eligible" : "In Progress";
    }

    function certificateHTML(s, { locked = false } = {}) {
        const p = Programmes.get(s.programmeId);
        const verifyUrl = `${TSCE_FLYER.website}/pages/verify.html`;
        return `<div class="certificate ${locked ? "locked" : ""}" role="img" aria-label="Certificate of completion for ${UI.esc(fullName(s))}">
            ${locked ? `<div class="cert-watermark">PREVIEW</div>` : ""}
            <div class="cert-inner">
                <div style="display:flex;flex-direction:column;align-items:center;gap:6px">${UI.logoFull("cert-logo")}<div class="cert-org">${TSCE_FLYER.name}</div><div class="cert-sub">${TSCE_FLYER.city}</div></div>
                <div><h2 class="cert-title">CERTIFICATE OF COMPLETION</h2><p class="cert-sub" style="margin-top:6px">This is to certify that</p></div>
                <div class="cert-name">${UI.esc(fullName(s))}</div>
                <div><p class="cert-sub">has successfully completed the ${p.weeks}-week professional programme</p><p class="cert-prog" style="margin-top:6px">${UI.esc(p.name)}</p><p class="cert-sub" style="margin-top:4px">${UI.esc(s.cohort)} · ${UI.date(s.startDate)} – ${UI.date(s.endDate)}</p></div>
                <div class="cert-foot">
                    <div class="sig" style="text-align:left"><b>Dr. Abubakar Sadiq</b>Director, TSCE</div>
                    <div class="cert-seal">TSCE<br>CERTIFIED<br>★</div>
                    <div class="sig" style="text-align:right"><b>${UI.esc(p.instructor)}</b>Lead Instructor</div>
                </div>
                <div class="cert-meta"><span>Certificate No: <b>${UI.esc(s.certificateNo)}</b></span><span>Issued: <b>${s.certificateIssuedAt ? UI.date(s.certificateIssuedAt) : "—"}</b></span><span>Verify: <b>${verifyUrl}</b></span></div>
            </div></div>`;
    }
    function printCertificate(s) { UI.printHTML(`Certificate ${s.certificateNo}`, `<style>@page{size:A4 landscape;margin:10mm}</style>${certificateHTML(s)}`); }
    /** Public check: { status: "valid" | "revoked" | "not_found", number, holder?, programme?, cohort?, issuedAt? } */
    function verify(no) {
        return API.get("certificates/verify", { no: String(no).trim() });
    }
    function verifyResultHTML(r) {
        if (!r) return "";
        const no = r.number;
        if (r.status === "valid") {
            return `<div class="card card-pad" style="border-color:rgba(18,161,80,.35);background:linear-gradient(135deg,#F3FCF6,#fff)"><div class="flex" style="align-items:flex-start"><span class="icon-tile green" style="width:56px;height:56px;font-size:1.4rem"><i class="fa-solid fa-shield-halved"></i></span><div style="flex:1"><div class="flex between flex-wrap"><h3 class="mb-0">Certificate verified</h3>${UI.badge("VERIFIED")}</div><p class="small muted">This certificate is authentic and was issued by ${UI.esc(Site.settings?.institution.name || TSCE_FLYER.name)}.</p>
                <div class="kv"><div><small>Holder</small><strong>${UI.esc(r.holder)}</strong></div><div><small>Certificate No.</small><strong class="mono">${UI.esc(r.number)}</strong></div><div><small>Programme</small><strong>${UI.esc(r.programme)}</strong></div><div><small>Issued</small><strong>${UI.date(r.issuedAt)}</strong></div><div><small>Cohort</small><strong>${UI.esc(r.cohort)}</strong></div></div></div></div></div>`;
        }
        if (r.status === "revoked") return `<div class="alert danger"><i class="fa-solid fa-ban"></i><p>Certificate <b>${UI.esc(no)}</b> has been <b>revoked</b> and is no longer valid. Contact TSCE for details.</p></div>`;
        return `<div class="alert danger"><i class="fa-solid fa-circle-xmark"></i><p>No certificate found with number <b>${UI.esc(no)}</b>. Check the number and try again, or contact TSCE.</p></div>`;
    }
    return { all, get, fullName, grade, gradeTone, attendance, results, modules, eligibility, certState, certificateHTML, printCertificate, verify, verifyResultHTML };
})();

/* Student not yet enrolled (admission pending) banner */
function pendingBanner(s) {
    if (s.status !== "Admission Pending") return "";
    return `<div class="alert warning mb-3"><i class="fa-solid fa-hourglass-half"></i><p><b>Admission under review.</b> Your payment is confirmed. The Admissions Office will confirm your enrolment shortly — classes begin ${UI.dateLong(s.startDate)}.</p></div>`;
}

/* ---------------- Student: Profile ---------------- */
Pages["student-profile"] = function (view, { student: s }) {
    const p = Programmes.get(s.programmeId);
    const qr = Array.from({ length: 49 }, (_, i) => { const x = i % 7, y = Math.floor(i / 7); const edge = (x < 2 && y < 2) || (x > 4 && y < 2) || (x < 2 && y > 4); return `<i class="${edge || (s.id.charCodeAt(i % s.id.length) + i) % 3 === 0 ? "" : "o"}"></i>`; }).join("");
    view.innerHTML = `${pendingBanner(s)}
        <div class="view-head"><div><h2>My Profile</h2><p>Your personal information and student identity.</p></div></div>
        <div class="dash-grid cols-12">
            <div class="span-4" style="display:grid;gap:20px;align-content:start">
                <div class="panel profile-card">${UI.avatar(Students.fullName(s), "xl")}<h3>${UI.esc(Students.fullName(s))}</h3><p class="muted small mb-2">${UI.esc(p.name)}</p>${UI.badge(s.status)}
                    <div class="divider"></div><div class="kv" style="text-align:left"><div><small>Student ID</small><strong class="mono">${UI.esc(s.id)}</strong></div><div><small>Cohort</small><strong>${UI.esc(s.cohort)}</strong></div></div></div>
                <div class="id-card"><div class="flex between">${UI.brand("#")}<span class="small" style="color:#9FB3EE">STUDENT ID</span></div>
                    <div class="idc-row">${UI.avatar(Students.fullName(s), "lg")}<div><strong>${UI.esc(Students.fullName(s))}</strong><small class="mono">${UI.esc(s.id)}</small><br><small>${UI.esc(p.code)} · Valid till ${UI.date(s.endDate, { month: "short", year: "numeric" })}</small></div><div class="qr" aria-hidden="true">${qr}</div></div></div>
            </div>
            <div class="panel span-8"><div class="panel-head"><h3><i class="fa-regular fa-id-card"></i>Personal information</h3><button class="btn btn-sm btn-soft" id="editProfile"><i class="fa-solid fa-pen"></i> Edit contact details</button></div>
                <div class="panel-body"><div class="kv">
                    <div><small>First name</small><strong>${UI.esc(s.firstName)}</strong></div><div><small>Last name</small><strong>${UI.esc(s.lastName)}</strong></div>
                    <div><small>Gender</small><strong>${UI.esc(s.gender)}</strong></div><div><small>Date of birth</small><strong>${UI.date(s.dob)}</strong></div>
                    <div><small>Email</small><strong>${UI.esc(s.email)}</strong></div><div><small>Phone</small><strong>${UI.esc(s.phone)}</strong></div>
                    <div class="full"><small>Address</small><strong>${UI.esc(s.address)}</strong></div>
                    <div><small>State of origin</small><strong>${UI.esc(s.state)}</strong></div><div><small>LGA</small><strong>${UI.esc(s.lga)}</strong></div>
                    <div><small>Highest qualification</small><strong>${UI.esc(s.qualification)}</strong></div><div><small>Institution</small><strong>${UI.esc(s.institution)}</strong></div>
                    <div class="full"><small>Emergency contact</small><strong>${UI.esc(s.emergencyContact || "—")}</strong></div>
                </div></div></div>
        </div>`;
    UI.$("#editProfile").onclick = () => {
        const m = UI.modal({
            title: "Edit contact details", size: "lg",
            body: `<form id="pf" class="form-grid" novalidate><div class="field"><label for="pf_p">Phone <span class="req">*</span></label><input id="pf_p" name="phone" class="input" data-type="phone" required value="${UI.esc(s.phone)}"></div>
                <div class="field"><label for="pf_e">Emergency contact</label><input id="pf_e" name="emergencyContact" class="input" value="${UI.esc(s.emergencyContact || "")}"></div>
                <div class="field span-2"><label for="pf_a">Address <span class="req">*</span></label><input id="pf_a" name="address" class="input" required value="${UI.esc(s.address)}"></div></form>
                <p class="hint mt-2">Name, date of birth and programme changes must be requested from the Admissions Office.</p>`,
            footer: `<button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-primary" id="pfSave">Save changes</button>`
        });
        UI.liveValidate(UI.$("#pf", m.el));
        UI.$("#pfSave", m.el).onclick = () => { const f = UI.$("#pf", m.el); if (!UI.validate(f)) return; DB.update("students", s.id, UI.formData(f)); m.close(); UI.toast("Profile updated", "Your contact details were saved.", "success"); Pages["student-profile"](view, { student: Students.get(s.id) }); };
    };
};

/* ---------------- Student: My Programme ---------------- */
Pages["student-programme"] = function (view, { student: s }) {
    const p = Programmes.get(s.programmeId);
    const mods = Students.modules(s);
    const current = mods.find((m) => m.pct < 100);
    const weeksDone = Math.max(0, Math.min(p.weeks, Math.ceil((Date.now() - new Date(s.startDate)) / (7 * 864e5))));
    view.innerHTML = `${pendingBanner(s)}
        <div class="view-head"><div><h2>My Programme</h2><p>${UI.esc(p.code)} · ${UI.esc(p.category)}</p></div><div class="actions"><a class="btn btn-outline" href="learning.html"><i class="fa-solid fa-play"></i> Continue learning</a></div></div>
        <div class="welcome"><div class="flex" style="gap:22px;align-items:center;position:relative;z-index:1">${UI.ring(s.progress, "complete")}<div><span class="badge badge-primary no-dot">${UI.esc(s.cohort)}</span><h2>${UI.esc(p.name)}</h2><p>${UI.esc(p.overview)}</p></div></div></div>
        <div class="kpis">
            ${[["Duration", `${p.weeks} weeks`, "fa-hourglass-half", ""], ["Start date", UI.date(s.startDate), "fa-calendar-plus", "cyan"], ["End date", UI.date(s.endDate), "fa-flag-checkered", "gold"], ["Instructor", UI.esc(s.instructor), "fa-chalkboard-user", "green"], ["Schedule", UI.esc(s.schedule.split(" (")[0]), "fa-clock", ""], ["Week", s.status === "Completed" ? "Completed" : `${weeksDone} of ${p.weeks}`, "fa-signal", "cyan"]]
            .map(([l, v, i, c]) => `<div class="kpi"><div class="kpi-top"><p class="label">${l}</p><span class="icon-tile ${c}"><i class="fa-solid ${i}"></i></span></div><div class="value" style="font-size:1.12rem">${v}</div></div>`).join("")}
        </div>
        <div class="dash-grid cols-12">
            <div class="panel span-8"><div class="panel-head"><div><h3><i class="fa-solid fa-list-check"></i>Module progress</h3><p>${mods.filter((m) => m.pct >= 100).length} of ${mods.length} modules completed</p></div></div>
                ${mods.map((m) => `<div class="module ${m.pct >= 100 ? "done" : m === current ? "current" : ""}"><div class="m-ic">${m.pct >= 100 ? '<i class="fa-solid fa-check"></i>' : String(m.index + 1).padStart(2, "0")}</div>
                    <div><h4>${UI.esc(m.name)}</h4><div class="progress sm ${m.pct >= 100 ? "green" : ""}"><span data-value="${m.pct}"></span></div></div>
                    <div class="m-status" style="color:${m.pct >= 100 ? "var(--success)" : m.pct > 0 ? "var(--primary)" : "var(--muted-2)"}">${m.pct >= 100 ? "✓ Completed" : m.pct > 0 ? m.pct + "% · In progress" : "Not started"}</div></div>`).join("")}
            </div>
            <div class="span-4" style="display:grid;gap:20px;align-content:start">
                <div class="panel"><div class="panel-head"><h3><i class="fa-solid fa-bullseye"></i>Learning outcomes</h3></div><div class="panel-body"><ul class="checklist">${p.outcomes.map((o) => `<li>${UI.esc(o)}</li>`).join("")}</ul></div></div>
                <div class="panel"><div class="panel-head"><h3><i class="fa-solid fa-briefcase"></i>Career pathways</h3></div><div class="panel-body"><div class="tag-list">${p.careers.map((c) => `<span class="chip">${UI.esc(c)}</span>`).join("")}</div></div></div>
            </div>
        </div>`;
    UI.animateAll(view);
};

/* ---------------- Student: Learning ---------------- */
Pages["student-learning"] = function (view, { student: s }) {
    const p = Programmes.get(s.programmeId);
    const mods = Students.modules(s);
    const current = mods.find((m) => m.pct < 100) || mods[mods.length - 1];
    const done = new Set(s.completedResources || []);
    const resources = (m) => [
        { id: `${m.index}-v`, icon: "fa-circle-play", tone: "", title: `${m.name}: Recorded lecture`, meta: "Video · 48 min" },
        { id: `${m.index}-s`, icon: "fa-file-lines", tone: "cyan", title: `${m.name}: Slides & notes`, meta: "PDF · 24 pages" },
        { id: `${m.index}-l`, icon: "fa-flask", tone: "gold", title: `${m.name}: Hands-on lab`, meta: "Practical · 2 hrs" },
        { id: `${m.index}-q`, icon: "fa-circle-question", tone: "green", title: `${m.name}: Knowledge check`, meta: "Quiz · 10 questions" }
    ];
    const days = ["Mon", "Wed", "Fri"];
    const upcoming = Array.from({ length: 4 }, (_, i) => { const d = new Date(Math.max(Date.now(), new Date(s.startDate))); let n = 0; while (n <= i) { d.setDate(d.getDate() + 1); if ([1, 3, 5].includes(d.getDay())) n++; } return d; });
    function render() {
        view.innerHTML = `${pendingBanner(s)}
        <div class="view-head"><div><h2>Learning</h2><p>Lessons, resources and upcoming classes for ${UI.esc(p.name)}.</p></div></div>
        <div class="welcome"><div style="position:relative;z-index:1"><span class="badge badge-primary no-dot">Current module · ${current.index + 1} of ${mods.length}</span><h2>${UI.esc(current.name)}</h2><div style="max-width:420px"><div class="flex between small mb-1"><span class="muted">Module progress</span><b>${current.pct}%</b></div><div class="progress"><span data-value="${current.pct}"></span></div></div></div>
            <div class="actions"><button class="btn btn-primary" id="resume"><i class="fa-solid fa-play"></i> Resume lesson</button></div></div>
        <div class="dash-grid cols-12">
            <div class="panel span-8"><div class="panel-head"><h3><i class="fa-solid fa-folder-open"></i>Module resources</h3><select class="select" id="modSel" style="width:auto;height:38px" aria-label="Choose module">${mods.map((m) => `<option value="${m.index}" ${m === current ? "selected" : ""}>${String(m.index + 1).padStart(2, "0")} · ${UI.esc(m.name)}</option>`).join("")}</select></div>
                <ul class="list" id="resList"></ul></div>
            <div class="panel span-4"><div class="panel-head"><h3><i class="fa-regular fa-calendar"></i>Upcoming classes</h3></div>
                ${upcoming.map((d, i) => `<div class="sched"><div class="d"><b>${d.getDate()}</b><small>${d.toLocaleDateString("en-GB", { month: "short" })}</small></div><div class="grow"><strong style="font-size:.9rem">${UI.esc(mods[Math.min(mods.length - 1, current.index + (i > 1 ? 1 : 0))].name)}</strong><div class="small muted">${days[[1, 3, 5].indexOf(d.getDay())] || ""} · ${UI.esc(s.schedule.split("(")[1]?.replace(")", "") || "9:00am")} · Lab 2</div></div></div>`).join("")}
            </div></div>`;
        const renderRes = (idx) => {
            const m = mods[idx];
            UI.$("#resList").innerHTML = resources(m).map((r) => `<li class="list-item"><span class="icon-tile ${r.tone}"><i class="fa-solid ${r.icon}"></i></span><div class="grow"><strong>${UI.esc(r.title)}</strong><small>${r.meta}</small></div>
                ${m.pct >= 100 || done.has(r.id) ? `<span class="badge badge-success">Completed</span>` : m.pct === 0 && idx > current.index ? `<span class="badge badge-neutral no-dot"><i class="fa-solid fa-lock"></i> Locked</span>` : `<button class="btn btn-xs btn-soft" data-res="${r.id}">Mark complete</button>`}</li>`).join("");
            UI.$$("[data-res]").forEach((b) => b.onclick = () => { done.add(b.dataset.res); DB.update("students", s.id, { completedResources: [...done] }); UI.toast("Nice work!", "Resource marked as complete.", "success"); renderRes(idx); });
        };
        UI.$("#modSel").onchange = (e) => renderRes(+e.target.value);
        UI.$("#resume").onclick = () => UI.modal({ title: `${UI.esc(current.name)} — Lesson`, subtitle: "Recorded lecture (demo player)", size: "lg", body: `<div style="aspect-ratio:16/9;border-radius:16px;background:var(--grad-navy);display:grid;place-items:center;color:#fff;text-align:center"><div><div style="width:72px;height:72px;border-radius:50%;background:rgba(255,255,255,.15);display:grid;place-items:center;margin:0 auto 12px;font-size:1.6rem"><i class="fa-solid fa-play"></i></div><b>${UI.esc(current.name)}</b><div class="small" style="color:#A9B9E6">Video content would stream from the LMS / video host</div></div></div>`, footer: `<button class="btn btn-primary" data-close>Close</button>` });
        renderRes(current.index);
        UI.animateAll(view);
    }
    render();
};

/* ---------------- Student: Attendance ---------------- */
Pages["student-attendance"] = function (view, { student: s }) {
    const a = Students.attendance(s.id);
    const months = [...new Set(a.recs.map((r) => r.date.slice(0, 7)))];
    let mi = months.length - 1;
    view.innerHTML = `${pendingBanner(s)}
        <div class="view-head"><div><h2>Attendance</h2><p>Your class attendance record. A minimum of 75% is required for certification.</p></div></div>
        <div class="kpis">
            <div class="kpi"><div class="kpi-top"><p class="label">Attendance rate</p><span class="icon-tile ${a.rate >= 75 ? "green" : "red"}"><i class="fa-solid fa-percent"></i></span></div><div class="value">${a.rate}%</div><div class="progress kpi-progress ${a.rate >= 75 ? "green" : ""}"><span data-value="${a.rate}"></span></div></div>
            <div class="kpi"><div class="kpi-top"><p class="label">Present</p><span class="icon-tile green"><i class="fa-solid fa-check"></i></span></div><div class="value">${a.present}</div><div class="small muted mt-1">of ${a.total} sessions</div></div>
            <div class="kpi"><div class="kpi-top"><p class="label">Late</p><span class="icon-tile gold"><i class="fa-solid fa-clock"></i></span></div><div class="value">${a.late}</div></div>
            <div class="kpi"><div class="kpi-top"><p class="label">Absent</p><span class="icon-tile red"><i class="fa-solid fa-xmark"></i></span></div><div class="value">${a.absent}</div></div>
        </div>
        ${a.total ? `<div class="dash-grid cols-12">
            <div class="panel span-5"><div class="panel-head"><h3 id="calTitle"></h3><div class="flex"><button class="icon-btn" id="calPrev" aria-label="Previous month"><i class="fa-solid fa-chevron-left"></i></button><button class="icon-btn" id="calNext" aria-label="Next month"><i class="fa-solid fa-chevron-right"></i></button></div></div>
                <div class="panel-body"><div class="cal" id="cal"></div><div class="cal-legend"><span><i style="background:var(--success-50);border:1px solid var(--success)"></i>Present</span><span><i style="background:var(--warning-50);border:1px solid var(--warning)"></i>Late</span><span><i style="background:var(--danger-50);border:1px solid var(--danger)"></i>Absent</span><span><i style="box-shadow:inset 0 0 0 2px var(--primary)"></i>Today</span></div></div></div>
            <div class="panel span-7"><div class="panel-head"><h3><i class="fa-solid fa-table-list"></i>Session log</h3></div><div id="attTable"></div></div>
        </div>` : `<div class="panel">${UI.empty({ icon: "fa-calendar-check", title: "No attendance records yet", text: `Attendance is recorded once classes begin on ${UI.dateLong(s.startDate)}.` })}</div>`}`;
    UI.animateAll(view);
    if (!a.total) return;
    function cal() {
        const [y, m] = months[mi].split("-").map(Number);
        const first = new Date(y, m - 1, 1), days = new Date(y, m, 0).getDate();
        const map = Object.fromEntries(a.recs.filter((r) => r.date.slice(0, 7) === months[mi]).map((r) => [new Date(r.date).getDate(), r]));
        const today = new Date();
        UI.$("#calTitle").innerHTML = `<i class="fa-regular fa-calendar"></i>${first.toLocaleDateString("en-GB", { month: "long", year: "numeric" })}`;
        const lead = (first.getDay() + 6) % 7;
        UI.$("#cal").innerHTML = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => `<div class="dow">${d}</div>`).join("") + Array.from({ length: lead }, () => `<div class="day empty"></div>`).join("") +
            Array.from({ length: days }, (_, i) => { const r = map[i + 1]; const isToday = today.getFullYear() === y && today.getMonth() === m - 1 && today.getDate() === i + 1; return `<div class="day ${r ? r.status.toLowerCase() : ""} ${isToday ? "today" : ""}" title="${r ? UI.esc(r.session + " — " + r.status) : ""}">${i + 1}</div>`; }).join("");
        UI.$("#calPrev").disabled = mi === 0; UI.$("#calNext").disabled = mi === months.length - 1;
    }
    UI.$("#calPrev").onclick = () => { mi--; cal(); }; UI.$("#calNext").onclick = () => { mi++; cal(); };
    cal();
    UI.dataTable("#attTable", {
        rows: [...a.recs].reverse(), pageSize: 8,
        columns: [{ key: "date", label: "Date", render: (r) => UI.date(r.date, { weekday: "short", day: "numeric", month: "short" }) }, { key: "session", label: "Course", render: (r) => UI.esc(r.session) }, { key: "status", label: "Status", render: (r) => UI.badge(r.status) }]
    });
};

/* ---------------- Student: Results & assessments ---------------- */
Pages["student-results"] = function (view, { student: s }) {
    const r = Students.results(s.id);
    const p = Programmes.get(s.programmeId);
    const assessed = new Set(r.recs.map((x) => x.module));
    const upcoming = Students.modules(s).filter((m) => !assessed.has(m.name)).slice(0, 4);
    view.innerHTML = `${pendingBanner(s)}
        <div class="view-head"><div><h2>Results</h2><p>Assessment scores for ${UI.esc(p.name)}. Grading: A 80+, B 70–79, C 60–69, D 50–59, F below 50.</p></div>
            <div class="actions"><button class="btn btn-outline" id="transcript" ${r.recs.length ? "" : "disabled"}><i class="fa-solid fa-print"></i> Print statement</button></div></div>
        <div class="kpis">
            <div class="kpi"><div class="kpi-top"><p class="label">Assessment average</p><span class="icon-tile"><i class="fa-solid fa-chart-line"></i></span></div><div class="value">${r.recs.length ? r.avg + "%" : "—"}</div><div class="mt-1">${r.recs.length ? `<span class="badge badge-${Students.gradeTone(r.grade)}">Grade ${r.grade}</span>` : ""}</div></div>
            <div class="kpi"><div class="kpi-top"><p class="label">Modules assessed</p><span class="icon-tile cyan"><i class="fa-solid fa-list-check"></i></span></div><div class="value">${r.recs.length} / ${p.modules.length}</div></div>
            <div class="kpi"><div class="kpi-top"><p class="label">Best module</p><span class="icon-tile gold"><i class="fa-solid fa-trophy"></i></span></div><div class="value" style="font-size:1.1rem">${r.best ? UI.esc(r.best.module) : "—"}</div><div class="small muted mt-1">${r.best ? r.best.score + "%" : ""}</div></div>
            <div class="kpi"><div class="kpi-top"><p class="label">Class rank (demo)</p><span class="icon-tile green"><i class="fa-solid fa-ranking-star"></i></span></div><div class="value">${r.recs.length ? (r.avg >= 84 ? "Top 10%" : r.avg >= 75 ? "Top 25%" : "Top 50%") : "—"}</div></div>
        </div>
        ${r.recs.length ? `<div class="dash-grid cols-12">
            <div class="panel span-7"><div class="panel-head"><div><h3><i class="fa-solid fa-chart-column"></i>Performance by module</h3><p>Your score vs class average</p></div></div><div class="panel-body"><div class="chart-box"><canvas id="resChart"></canvas></div></div></div>
            <div class="panel span-5" id="assessments"><div class="panel-head"><h3><i class="fa-solid fa-calendar-day"></i>Upcoming assessments</h3></div>
                ${upcoming.length ? upcoming.map((m, i) => { const d = new Date(); d.setDate(d.getDate() + 5 + i * 7); return `<div class="sched"><div class="d"><b>${d.getDate()}</b><small>${d.toLocaleDateString("en-GB", { month: "short" })}</small></div><div class="grow"><strong style="font-size:.9rem">${UI.esc(m.name)}</strong><div class="small muted">${i === upcoming.length - 1 && m.index === p.modules.length - 1 ? "Capstone presentation" : "Practical assessment"} · 100 marks</div></div>${UI.badge("Scheduled")}</div>`; }).join("") : UI.empty({ icon: "fa-flag-checkered", title: "All assessments completed" })}
            </div>
            <div class="panel span-12"><div class="panel-head"><h3><i class="fa-solid fa-table"></i>Assessment records</h3></div><div id="resTable"></div></div>
        </div>` : `<div class="panel" id="assessments">${UI.empty({ icon: "fa-chart-simple", title: "No results published yet", text: "Your assessment results will appear here as soon as instructors publish them." })}</div>`}`;
    if (!r.recs.length) return;
    const classAvg = r.recs.map((x) => { const peers = DB.where("results", (y) => y.programmeId === s.programmeId && y.module === x.module); return Math.round(peers.reduce((t, y) => t + y.score, 0) / peers.length); });
    Dashboard.chart("resChart", { type: "bar", data: { labels: r.recs.map((x) => x.module.length > 16 ? x.module.slice(0, 15) + "…" : x.module), datasets: [{ label: "My score", data: r.recs.map((x) => x.score), backgroundColor: r.recs.map((x) => x.score >= 80 ? "#1846D6" : x.score >= 70 ? "#0EA5E9" : "#F5B400"), borderRadius: 8, maxBarThickness: 34 }, { type: "line", label: "Class average", data: classAvg, borderColor: "#0B1D55", borderDash: [5, 4], pointRadius: 3, tension: .35, fill: false }] }, options: { scales: { y: { min: 0, max: 100 } } } });
    UI.dataTable("#resTable", {
        rows: r.recs, pageSize: 10,
        columns: [{ key: "module", label: "Module", render: (x) => `<b style="color:var(--text)">${UI.esc(x.module)}</b>` }, { key: "type", label: "Assessment" }, { key: "score", label: "Score", cls: "num", render: (x) => `<b>${x.score}</b>` }, { key: "grade", label: "Grade", render: (x) => `<span class="badge badge-${Students.gradeTone(x.grade)} no-dot">${x.grade}</span>` }, { key: "remark", label: "Remark", render: (x) => `<span class="small">${UI.esc(x.remark || "")}</span>` }, { key: "date", label: "Published", render: (x) => UI.date(x.date) }]
    });
    UI.$("#transcript").onclick = () => UI.printHTML("Statement of results", `<div class="receipt"><div class="receipt-head"><div class="flex">${UI.logoFull("receipt-logo")}<div><h3>${TSCE_FLYER.name}</h3><p>Statement of Results — ${UI.esc(Students.fullName(s))} (${UI.esc(s.id)})</p></div></div><div style="text-align:right"><p>${UI.esc(p.name)}</p><p>${UI.esc(s.cohort)}</p></div></div><table>${r.recs.map((x) => `<tr><td>${UI.esc(x.module)} · ${UI.esc(x.type)}</td><td>${x.score} (${x.grade})</td></tr>`).join("")}<tr class="r-total"><td>Average</td><td>${r.avg}% (${r.grade})</td></tr></table></div>`);
};

/* ---------------- Student: Certificates ---------------- */
Pages["student-certificates"] = function (view, { student: s }) {
    const state = Students.certState(s);
    const el = Students.eligibility(s);
    const issued = state === "Issued";
    view.innerHTML = `
        <div class="view-head"><div><h2>Certificates</h2><p>Your certificate of completion and public verification.</p></div>
            ${issued ? `<div class="actions"><button class="btn btn-outline" id="cShare"><i class="fa-solid fa-link"></i> Copy verify link</button><button class="btn btn-outline" id="cVerify"><i class="fa-solid fa-shield-halved"></i> Verify Certificate</button><button class="btn btn-primary" id="cPrint"><i class="fa-solid fa-download"></i> Download</button></div>` : ""}</div>
        <div class="dash-grid cols-12">
            <div class="span-8"><div style="position:relative">${Students.certificateHTML(s, { locked: !issued })}
                ${issued ? "" : `<div class="cert-lock" style="border-radius:10px"><div><span class="icon-tile" style="margin:0 auto 12px;width:60px;height:60px;border-radius:18px;font-size:1.4rem"><i class="fa-solid fa-lock"></i></span><h3 class="mb-1">Certificate ${state === "Eligible" ? "ready for issue" : "in progress"}</h3><p class="muted small" style="max-width:360px;margin:0 auto">${state === "Eligible" ? "You've met all requirements. The Academic Office will issue your certificate shortly." : `Complete your programme to unlock your certificate. You're <b>${s.progress}%</b> of the way there.`}</p></div></div>`}</div></div>
            <div class="span-4" style="display:grid;gap:20px;align-content:start">
                <div class="panel"><div class="panel-head"><h3><i class="fa-solid fa-certificate"></i>Status</h3>${UI.badge(issued ? "VERIFIED" : state)}</div><div class="panel-body">
                    <div class="kv"><div class="full"><small>Certificate number</small><strong class="mono">${UI.esc(s.certificateNo)}</strong></div><div><small>Issued</small><strong>${issued ? UI.date(s.certificateIssuedAt) : "—"}</strong></div><div><small>Programme</small><strong>${UI.esc(Programmes.name(s.programmeId))}</strong></div></div></div></div>
                <div class="panel"><div class="panel-head"><h3><i class="fa-solid fa-list-check"></i>Requirements</h3></div><ul class="list">${el.checks.map((c) => `<li class="list-item"><span class="icon-tile ${c.ok ? "green" : ""}" style="width:32px;height:32px;border-radius:50%;font-size:.75rem"><i class="fa-solid ${c.ok ? "fa-check" : "fa-hourglass-half"}"></i></span><div class="grow"><strong style="font-size:.86rem">${c.label}</strong></div><b class="small">${UI.esc(c.value)}</b></li>`).join("")}</ul></div>
                <div class="panel"><div class="panel-head"><h3><i class="fa-solid fa-shield-halved"></i>Verify any certificate</h3></div><div class="panel-body"><form id="vForm" class="flex"><input class="input" id="vNo" placeholder="TSCE/CERT/2026/00108" aria-label="Certificate number" style="flex:1"><button class="btn btn-primary">Verify</button></form><div id="vRes" class="mt-2"></div></div></div>
            </div></div>`;
    UI.$("#vForm").onsubmit = (e) => { e.preventDefault(); UI.$("#vRes").innerHTML = Students.verifyResultHTML(UI.$("#vNo").value); };
    if (issued) {
        UI.$("#cPrint").onclick = () => Students.printCertificate(s);
        UI.$("#cVerify").onclick = () => { UI.$("#vNo").value = s.certificateNo; UI.$("#vRes").innerHTML = Students.verifyResultHTML(s.certificateNo); UI.$("#vRes").scrollIntoView({ behavior: "smooth", block: "center" }); };
        UI.$("#cShare").onclick = () => UI.copy(location.href.replace(/pages\/student\/.*$/, "pages/verify.html?no=" + encodeURIComponent(s.certificateNo)));
    }
};

/* ---------------- Student: Support ---------------- */
Pages["student-support"] = function (view, { student: s }) {
    function render() {
        const tickets = DB.where("tickets", (t) => t.to === s.email).sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
        view.innerHTML = `<div class="view-head"><div><h2>Support</h2><p>Get help from the TSCE academic, admissions and ICT support teams.</p></div></div>
        <div class="dash-grid cols-12">
            <div class="panel span-7"><div class="panel-head"><h3><i class="fa-solid fa-headset"></i>Open a support ticket</h3></div><div class="panel-body">
                <form id="tForm" class="form-grid" novalidate>
                    <div class="field"><label for="t_c">Category</label><select id="t_c" name="category" class="select">${["Academic", "Learning", "Payments", "Certificates", "ICT / Portal", "Other"].map((c) => `<option>${c}</option>`).join("")}</select></div>
                    <div class="field"><label for="t_p">Priority</label><select id="t_p" name="priority" class="select"><option>Normal</option><option>High</option></select></div>
                    <div class="field span-2"><label for="t_s">Subject <span class="req">*</span></label><input id="t_s" name="subject" class="input" required></div>
                    <div class="field span-2"><label for="t_m">Message <span class="req">*</span></label><textarea id="t_m" name="message" class="textarea" required minlength="10"></textarea></div>
                    <div class="span-2"><button class="btn btn-primary"><i class="fa-solid fa-paper-plane"></i> Submit ticket</button></div>
                </form></div></div>
            <div class="span-5" style="display:grid;gap:20px;align-content:start">
                <div class="panel"><div class="panel-head"><h3><i class="fa-solid fa-ticket"></i>My tickets</h3></div>
                    ${tickets.length ? tickets.map((t) => `<div class="ticket"><span class="icon-tile ${t.status === "Resolved" ? "green" : "gold"}" style="width:36px;height:36px"><i class="fa-solid ${t.status === "Resolved" ? "fa-check" : "fa-clock"}"></i></span><div class="grow"><strong style="font-size:.88rem;display:block">${UI.esc(t.subject)}</strong><small class="muted">${t.id} · ${UI.esc(t.category)} · ${UI.date(t.createdAt)}</small>${t.reply ? `<div class="small mt-1" style="color:var(--text-2)"><i class="fa-solid fa-reply" style="color:var(--primary)"></i> ${UI.esc(t.reply)}</div>` : ""}</div>${UI.badge(t.status)}</div>`).join("") : UI.empty({ icon: "fa-ticket", title: "No tickets yet" })}</div>
                <div class="panel"><div class="panel-head"><h3><i class="fa-solid fa-phone"></i>Contact TSCE</h3></div><ul class="list">${TSCE_FLYER.phones.map((p) => `<li class="list-item"><span class="icon-tile"><i class="fa-solid fa-phone"></i></span><div class="grow"><strong>${p}</strong><small>Mon–Fri, 8:00am – 5:00pm</small></div><a class="btn btn-xs btn-soft" href="tel:${p.replace(/\s/g, "")}">Call</a></li>`).join("")}</ul></div>
            </div></div>`;
        const f = UI.$("#tForm");
        UI.liveValidate(f);
        f.onsubmit = (e) => {
            e.preventDefault(); if (!UI.validate(f)) return;
            const d = UI.formData(f);
            const id = "TKT-" + (1100 + DB.all("tickets").length);
            DB.insert("tickets", { id, to: s.email, subject: d.subject, category: d.category, priority: d.priority, message: d.message, status: "Open", createdAt: new Date().toISOString(), reply: null });
            Notifications.push("staff", "New support ticket", `${s.firstName} ${s.lastName}: ${d.subject}`, "support");
            UI.toast("Ticket submitted", `${id} — we'll respond within 24 hours.`, "success");
            render();
        };
    }
    render();
};

/* ---------------- Student: Settings ---------------- */
Pages["student-settings"] = function (view, { student: s, session }) {
    const prefs = { email: true, sms: true, push: false, results: true, ...(s.prefs || {}) };
    view.innerHTML = `<div class="view-head"><div><h2>Settings</h2><p>Security and notification preferences.</p></div></div>
        <div class="dash-grid cols-2">
            <div class="panel"><div class="panel-head"><h3><i class="fa-solid fa-key"></i>Change password</h3></div><div class="panel-body">
                <form id="pwForm" class="form-grid" novalidate style="grid-template-columns:1fr">
                    <div class="field"><label for="pw0">Current password <span class="req">*</span></label><input id="pw0" name="currentPassword" type="password" class="input" required autocomplete="current-password"></div>
                    <div class="field"><label for="pw1">New password <span class="req">*</span></label><input id="pw1" name="newPassword" type="password" class="input" required minlength="8" autocomplete="new-password"></div>
                    <div class="field"><label for="pw2">Confirm new password <span class="req">*</span></label><input id="pw2" type="password" class="input" required data-match="pw1" autocomplete="new-password"></div>
                    <div><button class="btn btn-primary">Update password</button></div></form></div></div>
            <div class="panel"><div class="panel-head"><h3><i class="fa-regular fa-bell"></i>Notifications</h3></div><div class="panel-body">
                ${[["email", "Email notifications", "Receipts, results and announcements"], ["sms", "SMS alerts", "Class reminders and payment alerts"], ["push", "Push notifications", "Browser notifications (coming soon)"], ["results", "Result alerts", "Notify me when results are published"]].map(([k, l, d]) => `<div class="setting-row"><div><strong>${l}</strong><small>${d}</small></div><label class="switch"><input type="checkbox" data-pref="${k}" ${prefs[k] ? "checked" : ""} aria-label="${l}"><span></span></label></div>`).join("")}
            </div></div></div>`;
    UI.$$("[data-pref]").forEach((c) => c.onchange = () => { prefs[c.dataset.pref] = c.checked; DB.update("students", s.id, { prefs }); UI.toast("Preferences saved", "", "success", 1800); });
    const f = UI.$("#pwForm");
    UI.liveValidate(f);
    f.onsubmit = async (e) => {
        e.preventDefault(); if (!UI.validate(f)) return;
        try {
            await Auth.changePassword(UI.$("#pw0").value, UI.$("#pw1").value);
            f.reset(); UI.toast("Password updated", "Use your new password next time you sign in.", "success");
        } catch (err) { if (!API.showFieldErrors(f, err)) UI.toast("Couldn't update password", err.message, "error"); }
    };
};

/* ---------------- Staff: Students ---------------- */
Pages["staff-students"] = function (view) {
    view.innerHTML = `
        <div class="view-head"><div><h2>Students</h2><p>Enrolled and graduated learners across all programmes and cohorts.</p></div>
            <div class="actions"><button class="btn btn-outline" id="stExport"><i class="fa-solid fa-file-csv"></i> Export CSV</button><a class="btn btn-primary" href="applications.html?status=Paid"><i class="fa-solid fa-user-plus"></i> Enrol from applications</a></div></div>
        <div class="kpis" id="stKpis"></div>
        <div class="panel"><div class="table-tools">
            <div class="input-icon"><i class="fa-solid fa-magnifying-glass"></i><input class="input" id="sSearch" placeholder="Search name, ID, email…" aria-label="Search students"></div>
            <select class="select" id="sProg" aria-label="Programme"><option value="">All programmes</option>${Programmes.all().map((p) => `<option value="${p.id}">${UI.esc(p.name)}</option>`).join("")}</select>
            <select class="select" id="sStatus" aria-label="Status"><option value="">All statuses</option><option>Active</option><option>Admission Pending</option><option>Completed</option><option>Suspended</option><option>Withdrawn</option></select>
            <select class="select" id="sCohort" aria-label="Cohort"><option value="">All cohorts</option>${[...new Set(Students.all().map((s) => s.cohort))].map((c) => `<option>${UI.esc(c)}</option>`).join("")}</select>
        </div><div id="stTable"></div></div>`;
    function kpis() {
        const S = Students.all();
        UI.$("#stKpis").innerHTML = [["Total students", S.length, "fa-users", ""], ["Active", S.filter((s) => s.status === "Active").length, "fa-user-check", "green"], ["Admission pending", S.filter((s) => s.status === "Admission Pending").length, "fa-hourglass-half", "gold"], ["Graduated", S.filter((s) => s.status === "Completed").length, "fa-graduation-cap", "cyan"]]
            .map(([l, v, i, c]) => `<div class="kpi"><div class="kpi-top"><p class="label">${l}</p><span class="icon-tile ${c}"><i class="fa-solid ${i}"></i></span></div><div class="value">${v}</div></div>`).join("");
    }
    const table = UI.dataTable("#stTable", {
        pageSize: 10, onRowClick: (id) => openStudent(id),
        onRender: (el) => UI.$$("[data-sact]", el).forEach((b) => b.onclick = (e) => { e.stopPropagation(); openStudent(b.dataset.id, b.dataset.sact); }),
        columns: [
            { key: "lastName", label: "Student", sortValue: (s) => s.firstName, render: (s) => `<div class="person">${UI.avatar(Students.fullName(s), "sm")}<div><strong>${UI.esc(Students.fullName(s))}</strong><small class="mono">${UI.esc(s.id)}</small></div></div>` },
            { key: "programmeId", label: "Programme", sortValue: (s) => Programmes.name(s.programmeId), render: (s) => `<span class="small">${UI.esc(Programmes.name(s.programmeId))}</span><div class="small muted">${UI.esc(s.cohort)}</div>` },
            { key: "progress", label: "Progress", render: (s) => `<div style="min-width:110px"><div class="flex between small"><b>${s.progress}%</b></div><div class="progress sm ${s.progress >= 100 ? "green" : ""}"><span style="width:${s.progress}%"></span></div></div>` },
            { key: "att", label: "Attendance", cls: "num", sortValue: (s) => Students.attendance(s.id).rate, render: (s) => { const a = Students.attendance(s.id); return a.total ? `<b style="color:${a.rate >= 75 ? "var(--success)" : "var(--danger)"}">${a.rate}%</b>` : "—"; } },
            { key: "avg", label: "Avg. score", cls: "num", sortValue: (s) => Students.results(s.id).avg, render: (s) => { const r = Students.results(s.id); return r.recs.length ? `<b>${r.avg}%</b>` : "—"; } },
            { key: "paymentStatus", label: "Payment", render: (s) => UI.badge(s.paymentStatus) },
            { key: "status", label: "Status", render: (s) => UI.badge(s.status) },
            { key: "", label: "Actions", sortable: false, render: (s) => `<div class="row-actions">${[["overview", "fa-eye", "View"], ["edit", "fa-pen", "Edit"], ["attendance", "fa-calendar-check", "Attendance"], ["results", "fa-chart-simple", "Results"], ["payments", "fa-naira-sign", "Payments"], ["certificate", "fa-certificate", "Certificate"]].map(([a, i, t]) => `<button class="icon-btn" data-sact="${a}" data-id="${UI.esc(s.id)}" title="${t}" aria-label="${t}"><i class="fa-solid ${i}"></i></button>`).join("")}</div>` }
        ],
        mobile: (s) => `<div class="m-row"><strong>${UI.esc(Students.fullName(s))}</strong>${UI.badge(s.status)}</div><div class="m-row"><span class="ref">${UI.esc(s.id)}</span><span>${s.progress}%</span></div><div class="m-row"><span>${UI.esc(Programmes.name(s.programmeId))}</span>${UI.badge(s.paymentStatus)}</div>`
    });
    function refresh() {
        const q = UI.$("#sSearch").value.toLowerCase(), pr = UI.$("#sProg").value, st = UI.$("#sStatus").value, co = UI.$("#sCohort").value;
        table.update(Students.all().filter((s) => (!pr || s.programmeId === pr) && (!st || s.status === st) && (!co || s.cohort === co) && [s.id, s.firstName, s.lastName, s.email, s.phone].join(" ").toLowerCase().includes(q)).sort((a, b) => a.firstName.localeCompare(b.firstName)), { resetPage: false });
        kpis();
    }
    function openStudent(id, tab = "overview") {
        if (tab === "edit") return edit(id);
        const s = Students.get(id);
        const p = Programmes.get(s.programmeId);
        const d = UI.drawer({
            title: UI.esc(Students.fullName(s)), subtitle: `<span class="mono">${UI.esc(s.id)}</span> · ${UI.badge(s.status)}`,
            body: `<div class="tabs mb-3" id="sTabs">${[["overview", "Overview"], ["attendance", "Attendance"], ["results", "Results"], ["payments", "Payments"], ["certificate", "Certificate"]].map(([k, l]) => `<button class="tab ${k === tab ? "active" : ""}" data-tab="${k}">${l}</button>`).join("")}</div><div id="sTabBody"></div>`,
            footer: `<button class="btn btn-ghost" id="sMsg"><i class="fa-regular fa-envelope"></i> Message</button><button class="btn btn-outline" id="sEdit"><i class="fa-solid fa-pen"></i> Edit</button>`
        });
        const body = UI.$("#sTabBody", d.el);
        function show(t) {
            UI.$$("#sTabs .tab", d.el).forEach((b) => b.classList.toggle("active", b.dataset.tab === t));
            const att = Students.attendance(s.id), res = Students.results(s.id), pays = Payments.forStudent(s);
            if (t === "overview") body.innerHTML = `<div class="flex mb-3" style="gap:18px">${UI.ring(s.progress, "progress", "sm")}<div><strong style="font-family:var(--font-head)">${UI.esc(p.name)}</strong><div class="small muted">${UI.esc(s.cohort)} · ${UI.esc(s.schedule)}</div><div class="small muted">Instructor: ${UI.esc(s.instructor)}</div></div></div>
                <div class="kv"><div><small>Email</small><strong>${UI.esc(s.email)}</strong></div><div><small>Phone</small><strong>${UI.esc(s.phone)}</strong></div><div><small>Gender</small><strong>${UI.esc(s.gender)}</strong></div><div><small>Date of birth</small><strong>${UI.date(s.dob)}</strong></div><div class="full"><small>Address</small><strong>${UI.esc(s.address)}</strong></div><div><small>State / LGA</small><strong>${UI.esc(s.state)} / ${UI.esc(s.lga)}</strong></div><div><small>Qualification</small><strong>${UI.esc(s.qualification)}</strong></div>
                <div><small>Attendance</small><strong>${att.total ? att.rate + "%" : "—"}</strong></div><div><small>Average</small><strong>${res.recs.length ? res.avg + "% (" + res.grade + ")" : "—"}</strong></div><div><small>Application</small><strong><a class="mono" href="applications.html?id=${encodeURIComponent(s.appId)}">${UI.esc(s.appId)}</a></strong></div><div><small>Discount</small><strong>${Applications.discountName(s.discountType)}</strong></div></div>`;
            if (t === "attendance") body.innerHTML = att.total ? `<div class="flex between mb-2"><b>${att.rate}% attendance</b><span class="small muted">${att.present} present · ${att.late} late · ${att.absent} absent</span></div><div class="progress mb-3 ${att.rate >= 75 ? "green" : ""}"><span style="width:${att.rate}%"></span></div>
                <div class="table-wrap"><table class="table"><thead><tr><th>Date</th><th>Session</th><th>Status</th></tr></thead><tbody>${[...att.recs].reverse().slice(0, 15).map((r) => `<tr><td>${UI.date(r.date)}</td><td>${UI.esc(r.session)}</td><td>${UI.badge(r.status)}</td></tr>`).join("")}</tbody></table></div>` : UI.empty({ icon: "fa-calendar", title: "No attendance yet" });
            if (t === "results") body.innerHTML = res.recs.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Module</th><th class="num">Score</th><th>Grade</th></tr></thead><tbody>${res.recs.map((r) => `<tr><td>${UI.esc(r.module)}</td><td class="num"><b>${r.score}</b></td><td><span class="badge badge-${Students.gradeTone(r.grade)} no-dot">${r.grade}</span></td></tr>`).join("")}<tr><td><b>Average</b></td><td class="num"><b>${res.avg}</b></td><td>${res.grade}</td></tr></tbody></table></div>` : UI.empty({ icon: "fa-chart-simple", title: "No results yet" });
            if (t === "payments") body.innerHTML = pays.length ? `<div class="table-wrap"><table class="table"><thead><tr><th>Reference</th><th class="num">Amount</th><th>Status</th><th></th></tr></thead><tbody>${pays.map((x) => `<tr><td><span class="ref">${UI.esc(x.ref)}</span><div class="small muted">${UI.date(x.createdAt)}</div></td><td class="num"><b>${UI.naira(x.amount)}</b></td><td>${UI.badge(x.status)}</td><td><button class="btn btn-xs btn-soft" data-rc="${UI.esc(x.ref)}">Receipt</button></td></tr>`).join("")}</tbody></table></div>` : UI.empty({ icon: "fa-receipt", title: "No payments" });
            if (t === "certificate") { const cs = Students.certState(s); body.innerHTML = `<div class="flex between mb-2"><b class="mono">${UI.esc(s.certificateNo)}</b>${UI.badge(cs)}</div><div style="transform:scale(.98)">${Students.certificateHTML(s, { locked: cs !== "Issued" })}</div><div class="mt-2"><a class="btn btn-soft btn-sm" href="certificates.html">Manage certificates →</a></div>`; }
            UI.$$("[data-rc]", body).forEach((b) => b.onclick = () => Payments.showReceipt(b.dataset.rc));
            UI.animateAll(body);
        }
        UI.$$("#sTabs .tab", d.el).forEach((b) => b.onclick = () => show(b.dataset.tab));
        UI.$("#sEdit", d.el).onclick = () => { d.close(); edit(id); };
        UI.$("#sMsg", d.el).onclick = () => {
            const m = UI.modal({ title: `Message ${UI.esc(s.firstName)}`, size: "sm", body: `<div class="field"><label for="msgT">Message</label><textarea id="msgT" class="textarea" required minlength="3"></textarea></div>`, footer: `<button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-primary" id="msgSend">Send</button>` });
            UI.$("#msgSend", m.el).onclick = () => { if (!UI.validate(m.body)) return; Notifications.push(s.email, "Message from TSCE", UI.$("#msgT", m.el).value, "announcement"); m.close(); UI.toast("Message sent", `Delivered to ${s.firstName}'s portal (and email, simulated).`, "success"); };
        };
        show(tab);
    }
    function edit(id) {
        const s = Students.get(id);
        const m = UI.modal({
            title: "Edit student", subtitle: UI.esc(s.id), size: "lg",
            body: `<form id="seForm" class="form-grid" novalidate>
                <div class="field"><label for="se_f">First name <span class="req">*</span></label><input id="se_f" name="firstName" class="input" required value="${UI.esc(s.firstName)}"></div>
                <div class="field"><label for="se_l">Last name <span class="req">*</span></label><input id="se_l" name="lastName" class="input" required value="${UI.esc(s.lastName)}"></div>
                <div class="field"><label for="se_e">Email <span class="req">*</span></label><input id="se_e" name="email" type="email" class="input" required value="${UI.esc(s.email)}"></div>
                <div class="field"><label for="se_p">Phone <span class="req">*</span></label><input id="se_p" name="phone" class="input" data-type="phone" required value="${UI.esc(s.phone)}"></div>
                <div class="field"><label for="se_s">Status</label><select id="se_s" name="status" class="select">${["Active", "Admission Pending", "Completed", "Suspended", "Withdrawn"].map((x) => `<option ${s.status === x ? "selected" : ""}>${x}</option>`).join("")}</select></div>
                <div class="field"><label for="se_sc">Schedule</label><select id="se_sc" name="schedule" class="select">${Programmes.get(s.programmeId).schedules.map((x) => `<option ${s.schedule === x ? "selected" : ""}>${x}</option>`).join("")}</select></div>
                <div class="field"><label for="se_pr">Progress (%)</label><input id="se_pr" name="progress" type="number" min="0" max="100" class="input" value="${s.progress}"></div>
                <div class="field"><label for="se_i">Instructor</label><input id="se_i" name="instructor" class="input" value="${UI.esc(s.instructor)}"></div>
                <div class="field span-2"><label for="se_a">Address</label><input id="se_a" name="address" class="input" value="${UI.esc(s.address)}"></div></form>`,
            footer: `<button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-primary" id="seSave">Save changes</button>`
        });
        UI.liveValidate(UI.$("#seForm", m.el));
        UI.$("#seSave", m.el).onclick = () => {
            const f = UI.$("#seForm", m.el); if (!UI.validate(f)) return;
            const d = UI.formData(f); d.progress = Math.max(0, Math.min(100, +d.progress));
            DB.update("students", id, d);
            m.close(); UI.toast("Student updated", `${d.firstName} ${d.lastName}`, "success"); refresh();
        };
    }
    ["#sProg", "#sStatus", "#sCohort"].forEach((x) => UI.$(x).addEventListener("change", refresh));
    UI.$("#sSearch").addEventListener("input", UI.debounce(refresh, 150));
    UI.$("#stExport").onclick = () => UI.downloadCSV("tsce-students.csv", Students.all().map((s) => ({ StudentID: s.id, Name: Students.fullName(s), Email: s.email, Phone: s.phone, Programme: Programmes.name(s.programmeId), Cohort: s.cohort, Progress: s.progress + "%", Attendance: Students.attendance(s.id).rate + "%", Average: Students.results(s.id).avg, Payment: s.paymentStatus, Status: s.status })));
    refresh();
    const open = UI.param("id"); if (open && Students.get(open)) openStudent(open);
};

/* ---------------- Staff: Attendance ---------------- */
Pages["staff-attendance"] = function (view) {
    const today = new Date().toISOString().slice(0, 10);
    const progs = Programmes.all().filter((p) => Students.all().some((s) => s.programmeId === p.id && s.status === "Active"));
    view.innerHTML = `
        <div class="view-head"><div><h2>Attendance</h2><p>Mark class attendance and monitor attendance trends by programme.</p></div>
            <div class="actions"><button class="btn btn-outline" id="attExport"><i class="fa-solid fa-file-csv"></i> Export</button></div></div>
        <div class="kpis" id="attKpis"></div>
        <div class="dash-grid cols-12">
            <div class="panel span-7"><div class="panel-head"><h3><i class="fa-solid fa-clipboard-user"></i>Take attendance</h3></div>
                <div class="table-tools"><select class="select" id="atProg" aria-label="Programme">${progs.map((p) => `<option value="${p.id}">${UI.esc(p.name)}</option>`).join("")}</select>
                    <input type="date" class="input" id="atDate" value="${today}" style="width:auto" aria-label="Date"><select class="select" id="atSession" aria-label="Session / module"></select>
                    <span class="spacer"></span><button class="btn btn-sm btn-soft" id="allPresent"><i class="fa-solid fa-check-double"></i> All present</button></div>
                <div id="roster"></div>
                <div class="table-foot"><span id="rosterSummary"></span><button class="btn btn-primary" id="saveAtt"><i class="fa-solid fa-floppy-disk"></i> Save attendance</button></div></div>
            <div class="panel span-5"><div class="panel-head"><div><h3><i class="fa-solid fa-chart-bar"></i>Attendance by programme</h3><p>Active cohort average</p></div></div><div class="panel-body"><div class="chart-box lg"><canvas id="attByProg"></canvas></div></div></div>
        </div>`;
    let marks = {};
    function kpis() {
        const recs = DB.all("attendance");
        const recent = recs.filter((r) => (Date.now() - new Date(r.date)) < 14 * 864e5);
        const rate = (rs) => rs.length ? Math.round(rs.filter((r) => r.status !== "Absent").length / rs.length * 100) : 0;
        const below = Students.all().filter((s) => s.status === "Active" && Students.attendance(s.id).total && Students.attendance(s.id).rate < 75);
        UI.$("#attKpis").innerHTML = [["Overall attendance", rate(recs) + "%", "fa-percent", "green"], ["Last 14 days", rate(recent) + "%", "fa-calendar-week", ""], ["Sessions recorded", UI.num(recs.length), "fa-list-check", "cyan"], ["Below 75% threshold", below.length, "fa-triangle-exclamation", "red"]]
            .map(([l, v, i, c]) => `<div class="kpi"><div class="kpi-top"><p class="label">${l}</p><span class="icon-tile ${c}"><i class="fa-solid ${i}"></i></span></div><div class="value">${v}</div></div>`).join("");
    }
    function roster() {
        const pid = UI.$("#atProg").value, date = UI.$("#atDate").value;
        const p = Programmes.get(pid);
        const sessSel = UI.$("#atSession");
        if (sessSel.dataset.pid !== pid) { sessSel.innerHTML = p.modules.map((m) => `<option>${UI.esc(m)}</option>`).join(""); sessSel.dataset.pid = pid; const cur = Students.all().find((s) => s.programmeId === pid && s.status === "Active"); if (cur) { const i = (cur.moduleProgress || []).findIndex((x) => x < 100); if (i >= 0) sessSel.selectedIndex = i; } }
        const list = Students.all().filter((s) => s.programmeId === pid && s.status === "Active");
        marks = {};
        list.forEach((s) => { const ex = DB.first("attendance", (a) => a.studentId === s.id && a.date.slice(0, 10) === date); marks[s.id] = ex ? ex.status : "Present"; });
        UI.$("#roster").innerHTML = list.length ? `<ul class="list">${list.map((s) => `<li class="list-item">${UI.avatar(Students.fullName(s), "sm")}<div class="grow"><strong>${UI.esc(Students.fullName(s))}</strong><small class="mono">${UI.esc(s.id)} · ${Students.attendance(s.id).rate}% overall</small></div>
            <div class="tabs" role="radiogroup" aria-label="Attendance for ${UI.esc(s.firstName)}">${["Present", "Late", "Absent"].map((st) => `<button class="tab ${marks[s.id] === st ? "active" : ""}" data-sid="${UI.esc(s.id)}" data-st="${st}" role="radio" aria-checked="${marks[s.id] === st}" style="${marks[s.id] === st ? `color:${st === "Present" ? "var(--success)" : st === "Late" ? "#B06E00" : "var(--danger)"}` : ""}">${st}</button>`).join("")}</div></li>`).join("")}</ul>`
            : UI.empty({ icon: "fa-users-slash", title: "No active students", text: "There are no active students in this programme." });
        UI.$$("#roster [data-sid]").forEach((b) => b.onclick = () => { marks[b.dataset.sid] = b.dataset.st; const row = b.parentElement; UI.$$("button", row).forEach((x) => { const on = x === b; x.classList.toggle("active", on); x.setAttribute("aria-checked", on); x.style.color = on ? (x.dataset.st === "Present" ? "var(--success)" : x.dataset.st === "Late" ? "#B06E00" : "var(--danger)") : ""; }); summary(); });
        summary();
    }
    function summary() { const v = Object.values(marks); UI.$("#rosterSummary").innerHTML = `<b>${v.filter((x) => x === "Present").length}</b> present · <b>${v.filter((x) => x === "Late").length}</b> late · <b>${v.filter((x) => x === "Absent").length}</b> absent`; }
    function chart() {
        const data = progs.map((p) => { const rs = DB.where("attendance", (a) => a.programmeId === p.id); return rs.length ? Math.round(rs.filter((r) => r.status !== "Absent").length / rs.length * 100) : 0; });
        Dashboard.chart("attByProg", { type: "bar", data: { labels: progs.map((p) => p.name.length > 22 ? p.name.slice(0, 20) + "…" : p.name), datasets: [{ data, backgroundColor: data.map((v) => v >= 90 ? "#12A150" : v >= 80 ? "#1846D6" : "#F5B400"), borderRadius: 6, maxBarThickness: 18 }] }, options: { indexAxis: "y", plugins: { legend: { display: false } }, scales: { x: { min: 50, max: 100, ticks: { callback: (v) => v + "%" } } } } });
    }
    UI.$("#atProg").onchange = roster; UI.$("#atDate").onchange = roster;
    UI.$("#allPresent").onclick = () => UI.$$("#roster [data-st='Present']").forEach((b) => b.click());
    UI.$("#saveAtt").onclick = () => {
        const pid = UI.$("#atProg").value, date = UI.$("#atDate").value, sess = UI.$("#atSession").value;
        if (!Object.keys(marks).length) return UI.toast("Nothing to save", "No students on this roster.", "warning");
        const iso = new Date(date + "T09:00:00").toISOString();
        const rows = DB.all("attendance").filter((a) => !(marks[a.studentId] && a.date.slice(0, 10) === date));
        Object.entries(marks).forEach(([sid, st]) => {
            rows.push({ id: `ATT-${sid}-${date}`, studentId: sid, programmeId: pid, date: iso, session: sess, status: st });
            if (st === "Absent") Notifications.push(Students.get(sid).email, "Missed class", `You were marked absent for ${sess} on ${UI.date(iso)}.`, "attendance");
        });
        DB.save("attendance", rows);
        UI.toast("Attendance saved", `${Object.keys(marks).length} students · ${Programmes.name(pid)} · ${UI.date(iso)}`, "success");
        kpis(); chart();
    };
    UI.$("#attExport").onclick = () => UI.downloadCSV("tsce-attendance.csv", DB.all("attendance").map((a) => { const s = Students.get(a.studentId); return { Date: UI.date(a.date), StudentID: a.studentId, Student: s ? Students.fullName(s) : "", Programme: Programmes.name(a.programmeId), Session: a.session, Status: a.status }; }));
    if (!progs.length) { UI.$("#roster").innerHTML = UI.empty({ icon: "fa-users-slash", title: "No active classes" }); return; }
    kpis(); roster(); chart();
};

/* ---------------- Staff: Assessments ---------------- */
Pages["staff-assessments"] = function (view) {
    const progs = Programmes.all().filter((p) => Students.all().some((s) => s.programmeId === p.id));
    view.innerHTML = `
        <div class="view-head"><div><h2>Assessments</h2><p>Enter scores, publish results to students and monitor performance.</p></div>
            <div class="actions"><button class="btn btn-outline" id="resExport"><i class="fa-solid fa-file-csv"></i> Export results</button></div></div>
        <div class="kpis" id="asKpis"></div>
        <div class="dash-grid cols-12">
            <div class="panel span-7"><div class="panel-head"><div><h3><i class="fa-solid fa-pen-to-square"></i>Gradebook</h3><p>Scores are out of 100</p></div></div>
                <div class="table-tools"><select class="select" id="gbProg" aria-label="Programme">${progs.map((p) => `<option value="${p.id}">${UI.esc(p.name)}</option>`).join("")}</select><select class="select" id="gbMod" aria-label="Module"></select><select class="select" id="gbType" aria-label="Assessment type"><option>Practical Assignment</option><option>Module Test</option><option>Project</option><option>Capstone Project</option></select></div>
                <div id="gradebook"></div>
                <div class="table-foot"><span id="gbAvg"></span><div class="flex"><button class="btn btn-outline" id="gbDraft">Save draft</button><button class="btn btn-primary" id="gbPublish"><i class="fa-solid fa-paper-plane"></i> Publish results</button></div></div></div>
            <div class="panel span-5"><div class="panel-head"><div><h3><i class="fa-solid fa-chart-pie"></i>Grade distribution</h3><p>All published assessments</p></div></div><div class="panel-body"><div class="chart-box"><canvas id="gradeDist"></canvas></div></div></div>
            <div class="panel span-12"><div class="panel-head"><h3><i class="fa-solid fa-clock-rotate-left"></i>Recently published</h3></div><div id="recentRes"></div></div>
        </div>`;
    function kpis() {
        const R = DB.where("results", (r) => r.status === "Published");
        const avg = R.length ? Math.round(R.reduce((t, r) => t + r.score, 0) / R.length) : 0;
        UI.$("#asKpis").innerHTML = [["Assessment records", R.length, "fa-file-signature", ""], ["Average score", avg + "%", "fa-chart-line", "green"], ["Distinctions (A)", R.filter((r) => r.grade === "A").length, "fa-trophy", "gold"], ["Needs support (<50)", R.filter((r) => r.score < 50).length, "fa-life-ring", "red"]]
            .map(([l, v, i, c]) => `<div class="kpi"><div class="kpi-top"><p class="label">${l}</p><span class="icon-tile ${c}"><i class="fa-solid ${i}"></i></span></div><div class="value">${v}</div></div>`).join("");
    }
    function mods() {
        const p = Programmes.get(UI.$("#gbProg").value);
        UI.$("#gbMod").innerHTML = p.modules.map((m) => `<option>${UI.esc(m)}</option>`).join("");
        const cur = Students.all().find((s) => s.programmeId === p.id && s.status === "Active");
        if (cur) { const i = (cur.moduleProgress || []).findIndex((x) => x < 100); if (i > 0) UI.$("#gbMod").selectedIndex = i - 1; }
        book();
    }
    function book() {
        const pid = UI.$("#gbProg").value, mod = UI.$("#gbMod").value;
        const list = Students.all().filter((s) => s.programmeId === pid && ["Active", "Completed"].includes(s.status));
        UI.$("#gradebook").innerHTML = list.length ? `<ul class="list">${list.map((s) => { const ex = DB.first("results", (r) => r.studentId === s.id && r.module === mod); return `<li class="list-item">${UI.avatar(Students.fullName(s), "sm")}<div class="grow"><strong>${UI.esc(Students.fullName(s))}</strong><small>${ex ? `${UI.badge(ex.status)} · ${ex.type}` : "Not graded"}</small></div><div class="field" style="width:96px"><label class="sr-only" for="sc_${s.id}">Score for ${UI.esc(s.firstName)}</label><input id="sc_${s.id}" class="input" type="number" min="0" max="100" data-score="${UI.esc(s.id)}" value="${ex ? ex.score : ""}" placeholder="—" style="height:40px;text-align:center"></div><span class="badge no-dot" data-grade="${UI.esc(s.id)}" style="min-width:34px;justify-content:center">${ex ? ex.grade : "–"}</span></li>`; }).join("")}</ul>`
            : UI.empty({ icon: "fa-users", title: "No students in this programme" });
        UI.$$("[data-score]").forEach((i) => i.addEventListener("input", () => { const v = +i.value; const g = i.value === "" ? "–" : Students.grade(v); const b = UI.$(`[data-grade="${CSS.escape(i.dataset.score)}"]`); b.textContent = g; b.className = `badge no-dot badge-${g === "–" ? "neutral" : Students.gradeTone(g)}`; avg(); }));
        UI.$$("[data-grade]").forEach((b) => { if (b.textContent !== "–") b.classList.add("badge-" + Students.gradeTone(b.textContent)); });
        avg();
    }
    function avg() { const v = UI.$$("[data-score]").map((i) => i.value).filter((x) => x !== "").map(Number); UI.$("#gbAvg").innerHTML = v.length ? `Class average: <b>${Math.round(v.reduce((a, b) => a + b, 0) / v.length)}%</b> · ${v.length} graded` : "Enter scores to see the class average"; }
    function save(status) {
        const pid = UI.$("#gbProg").value, mod = UI.$("#gbMod").value, type = UI.$("#gbType").value;
        const inputs = UI.$$("[data-score]").filter((i) => i.value !== "");
        if (!inputs.length) return UI.toast("No scores entered", "Enter at least one score.", "warning");
        const bad = inputs.find((i) => +i.value < 0 || +i.value > 100);
        if (bad) { bad.focus(); return UI.toast("Invalid score", "Scores must be between 0 and 100.", "error"); }
        const rows = DB.all("results");
        inputs.forEach((i) => {
            const sid = i.dataset.score, sc = +i.value, idx = rows.findIndex((r) => r.studentId === sid && r.module === mod);
            const rec = { id: idx >= 0 ? rows[idx].id : `RES-${sid}-${Date.now().toString(36)}`, studentId: sid, programmeId: pid, module: mod, type, score: sc, grade: Students.grade(sc), status, date: new Date().toISOString(), remark: sc >= 85 ? "Excellent work" : sc >= 70 ? "Very good" : sc >= 60 ? "Good — keep practising" : sc >= 50 ? "Fair" : "Needs improvement" };
            if (idx >= 0) rows[idx] = rec; else rows.push(rec);
            if (status === "Published") Notifications.push(Students.get(sid).email, "Result published", `Your assessment result for ${mod} has been published.`, "result");
        });
        DB.save("results", rows);
        UI.toast(status === "Published" ? "Results published" : "Draft saved", `${inputs.length} scores · ${mod}`, "success");
        book(); kpis(); dist(); recent();
    }
    function dist() {
        const R = DB.where("results", (r) => r.status === "Published");
        const g = ["A", "B", "C", "D", "F"];
        Dashboard.chart("gradeDist", { type: "doughnut", data: { labels: g.map((x) => "Grade " + x), datasets: [{ data: g.map((x) => R.filter((r) => r.grade === x).length), backgroundColor: ["#12A150", "#1846D6", "#06C8E0", "#F5B400", "#DC2F45"], borderWidth: 0 }] }, options: { cutout: "64%", plugins: { legend: { position: "bottom" } } } });
    }
    function recent() {
        UI.dataTable("#recentRes", {
            rows: DB.where("results", (r) => r.status === "Published").sort((a, b) => new Date(b.date) - new Date(a.date)), pageSize: 8,
            columns: [{ key: "studentId", label: "Student", render: (r) => { const s = Students.get(r.studentId); return s ? `<div class="person">${UI.avatar(Students.fullName(s), "sm")}<div><strong>${UI.esc(Students.fullName(s))}</strong><small class="mono">${UI.esc(s.id)}</small></div></div>` : r.studentId; } }, { key: "programmeId", label: "Programme", render: (r) => `<span class="small">${UI.esc(Programmes.name(r.programmeId))}</span>` }, { key: "module", label: "Module" }, { key: "type", label: "Type", render: (r) => `<span class="small">${UI.esc(r.type)}</span>` }, { key: "score", label: "Score", cls: "num", render: (r) => `<b>${r.score}</b>` }, { key: "grade", label: "Grade", render: (r) => `<span class="badge badge-${Students.gradeTone(r.grade)} no-dot">${r.grade}</span>` }, { key: "date", label: "Date", render: (r) => UI.date(r.date) }]
        });
    }
    UI.$("#gbProg").onchange = mods; UI.$("#gbMod").onchange = book;
    UI.$("#gbDraft").onclick = () => save("Draft"); UI.$("#gbPublish").onclick = () => save("Published");
    UI.$("#resExport").onclick = () => UI.downloadCSV("tsce-results.csv", DB.all("results").map((r) => { const s = Students.get(r.studentId); return { StudentID: r.studentId, Student: s ? Students.fullName(s) : "", Programme: Programmes.name(r.programmeId), Module: r.module, Type: r.type, Score: r.score, Grade: r.grade, Status: r.status, Date: UI.date(r.date) }; }));
    kpis(); mods(); dist(); recent();
};

/* ---------------- Staff: Certificates ---------------- */
Pages["staff-certificates"] = function (view) {
    let filter = "";
    view.innerHTML = `
        <div class="view-head"><div><h2>Certificates</h2><p>Track eligibility, issue certificates of completion and verify authenticity.</p></div></div>
        <div class="stat-chips" id="certChips"></div>
        <div class="dash-grid cols-12">
            <div class="panel span-8"><div class="table-tools"><div class="input-icon"><i class="fa-solid fa-magnifying-glass"></i><input class="input" id="cSearch" placeholder="Search student or certificate no…" aria-label="Search certificates"></div></div><div id="certTable"></div></div>
            <div class="panel span-4"><div class="panel-head"><h3><i class="fa-solid fa-shield-halved"></i>Verify certificate</h3></div><div class="panel-body"><form id="cvForm" class="flex"><input class="input" id="cvNo" placeholder="TSCE/CERT/2026/00108" aria-label="Certificate number" style="flex:1"><button class="btn btn-primary">Verify</button></form><div id="cvRes" class="mt-2"></div><p class="hint mt-2">Public verification page: <a href="../verify.html" target="_blank" rel="noopener">verify.html</a></p></div></div>
        </div>`;
    function chips() {
        const S = Students.all(); const c = (st) => S.filter((s) => Students.certState(s) === st).length;
        UI.$("#certChips").innerHTML = [["", "All", S.length], ["Issued", "Issued", c("Issued")], ["Eligible", "Eligible", c("Eligible")], ["In Progress", "In progress", c("In Progress")]].map(([v, l, n]) => `<button class="stat-chip ${filter === v ? "active" : ""}" data-f="${v}">${l} <b>${n}</b></button>`).join("");
        UI.$$("#certChips .stat-chip").forEach((b) => b.onclick = () => { filter = b.dataset.f; refresh(); });
    }
    const table = UI.dataTable("#certTable", {
        pageSize: 10, onRowClick: (id) => preview(id),
        onRender: (el) => UI.$$("[data-issue]", el).forEach((b) => b.onclick = (e) => { e.stopPropagation(); issue(b.dataset.issue); }),
        columns: [
            { key: "lastName", label: "Student", sortValue: (s) => s.firstName, render: (s) => `<div class="person">${UI.avatar(Students.fullName(s), "sm")}<div><strong>${UI.esc(Students.fullName(s))}</strong><small>${UI.esc(Programmes.name(s.programmeId))}</small></div></div>` },
            { key: "certificateNo", label: "Certificate No.", render: (s) => `<span class="ref">${UI.esc(s.certificateNo)}</span>` },
            { key: "progress", label: "Progress", cls: "num", render: (s) => `${s.progress}%` },
            { key: "state", label: "Status", sortValue: (s) => Students.certState(s), render: (s) => UI.badge(Students.certState(s)) + (s.certificateIssuedAt ? `<div class="small muted">${UI.date(s.certificateIssuedAt)}</div>` : "") },
            { key: "", label: "", sortable: false, render: (s) => { const st = Students.certState(s); return st === "Issued" ? `<button class="btn btn-xs btn-soft">View</button>` : `<button class="btn btn-xs ${st === "Eligible" ? "btn-primary" : "btn-outline"}" data-issue="${UI.esc(s.id)}">${st === "Eligible" ? "Issue" : "Issue early"}</button>`; } }
        ]
    });
    function refresh() {
        const q = UI.$("#cSearch").value.toLowerCase();
        table.update(Students.all().filter((s) => (!filter || Students.certState(s) === filter) && (Students.fullName(s) + s.certificateNo + s.id).toLowerCase().includes(q)).sort((a, b) => ["Eligible", "In Progress", "Issued"].indexOf(Students.certState(a)) - ["Eligible", "In Progress", "Issued"].indexOf(Students.certState(b))), { resetPage: false });
        chips();
    }
    async function issue(id) {
        const s = Students.get(id);
        const el = Students.eligibility(s);
        if (!el.eligible) {
            const missing = el.checks.filter((c) => !c.ok).map((c) => `• ${c.label} (${c.value})`).join("<br>");
            if (!(await UI.confirm({ title: "Issue before completion?", message: `${UI.esc(Students.fullName(s))} hasn't met all requirements:<br><span class="small">${missing}</span><br><br>Issuing now marks the programme as completed.`, confirmText: "Override & issue", tone: "danger", icon: "fa-triangle-exclamation" }))) return;
        }
        DB.update("students", id, { certificateStatus: "Issued", certificateIssuedAt: new Date().toISOString(), progress: 100, status: "Completed", moduleProgress: (s.moduleProgress || []).map(() => 100) });
        Notifications.push(s.email, "Certificate issued", `Your certificate of completion (${s.certificateNo}) is ready. Congratulations!`, "certificate");
        UI.toast("Certificate issued", `${s.certificateNo} — ${Students.fullName(s)}`, "success");
        UI.confetti(); refresh();
    }
    function preview(id) {
        const s = Students.get(id); const st = Students.certState(s);
        const m = UI.modal({ title: "Certificate preview", subtitle: `${UI.esc(s.certificateNo)} · ${st}`, size: "xl", body: Students.certificateHTML(s, { locked: st !== "Issued" }),
            footer: `<button class="btn btn-ghost" data-close>Close</button>${st === "Issued" ? `<button class="btn btn-soft-danger" id="cRevoke">Revoke</button><button class="btn btn-primary" id="cPr"><i class="fa-solid fa-print"></i> Print</button>` : `<button class="btn btn-primary" id="cIss">Issue certificate</button>`}` });
        UI.$("#cPr", m.el)?.addEventListener("click", () => Students.printCertificate(s));
        UI.$("#cIss", m.el)?.addEventListener("click", () => { m.close(); issue(id); });
        UI.$("#cRevoke", m.el)?.addEventListener("click", async () => { if (!(await UI.confirm({ title: "Revoke certificate?", message: "Verification will fail for this certificate number.", confirmText: "Revoke", tone: "danger", icon: "fa-ban" }))) return; DB.update("students", id, { certificateStatus: "Revoked" }); m.close(); UI.toast("Certificate revoked", s.certificateNo, "warning"); refresh(); });
    }
    UI.$("#cSearch").addEventListener("input", UI.debounce(refresh, 150));
    UI.$("#cvForm").onsubmit = async (e) => {
        e.preventDefault();
        try { UI.$("#cvRes").innerHTML = Students.verifyResultHTML(await Students.verify(UI.$("#cvNo").value)); }
        catch (err) { UI.toast("Verification failed", err.message, "error"); }
    };
    refresh();
};

/* ---------------- Public: Verify certificate ---------------- */
Pages["verify"] = function () {
    const f = UI.$("#verifyForm"), i = UI.$("#verifyNo"), out = UI.$("#verifyResult");
    const run = async () => {
        out.innerHTML = UI.skeleton(3);
        try { out.innerHTML = Students.verifyResultHTML(await Students.verify(i.value)); }
        catch (err) { out.innerHTML = `<div class="alert danger"><i class="fa-solid fa-circle-exclamation"></i><p>${UI.esc(err.message)}</p></div>`; }
    };
    f.onsubmit = (e) => { e.preventDefault(); if (!i.value.trim()) { UI.fieldError(i, "Enter a certificate number."); return; } UI.fieldError(i, ""); run(); };
    if (UI.param("no")) { i.value = UI.param("no"); run(); }
};
