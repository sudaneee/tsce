/* ==========================================================================
   TSCE — Applications, Discount engine, Scholarships
   ========================================================================== */

/* ---------------- Discount engine ----------------
   Rules from the TSCE flyer:
     • Early Bird 15%  — payment before 1 October 2026 (applied automatically)
     • Excellence 50%  — WAEC 2020-date with 5 A's or more (staff verifies)
     • Scholarship ≤40% — performance at intake exam/interview (staff assigns)
   Discounts do NOT stack: the single highest approved discount applies. */
const Discounts = (() => {
    // Percentages, thresholds and the early-bird state come from the server
    // (Site.settings). The browser clock is never trusted for money.
    const cfg = () => Site.settings?.discounts || { earlybird: 15, excellence: 50, scholarshipMax: 40, excellenceMinYear: 2020, excellenceMinAs: 5, earlyBirdOpen: false };
    const deadline = () => Site.day(Site.settings?.admissions?.earlyBirdDeadline);
    const lastDay = () => { const d = deadline(); if (!d) return null; d.setDate(d.getDate() - 1); return d; };
    function rules() {
        const c = cfg();
        return {
            earlybird: { id: "earlybird", name: "Early Bird Discount", pct: c.earlybird, icon: "fa-bolt", condition: deadline() ? `Payment before ${UI.dateLong(deadline())}` : "Payment before the early-bird deadline", mode: "automatic" },
            excellence: { id: "excellence", name: "Excellence Award", pct: c.excellence, icon: "fa-award", condition: `WAEC results from ${c.excellenceMinYear} to date with ${c.excellenceMinAs} A's or more`, mode: "verification" },
            scholarship: { id: "scholarship", name: "Performance Scholarship", pct: c.scholarshipMax, upTo: true, icon: "fa-graduation-cap", condition: "Excellent performance during intake examination / interview", mode: "assessment" }
        };
    }
    const earlyBirdOpen = () => !!cfg().earlyBirdOpen;
    const excellenceEligible = (d) => d.waecStatus === "Available" && +d.waecYear >= cfg().excellenceMinYear && +d.numAs >= cfg().excellenceMinAs;

    function evaluate(d) {
        const R = rules(), c = cfg(), eb = earlyBirdOpen(), ex = excellenceEligible(d);
        return [
            { ...R.earlybird, eligible: eb, reason: eb ? `You qualify — pay before ${UI.dateLong(deadline())}.` : lastDay() ? `The early-bird window closed on ${UI.dateLong(lastDay())}.` : "The early-bird offer has closed." },
            { ...R.excellence, eligible: ex, reason: ex ? `WAEC ${d.waecYear} with ${d.numAs} A's — eligible, subject to result verification.` : `Requires WAEC (${c.excellenceMinYear} or later) with at least ${c.excellenceMinAs} A's.` },
            { ...R.scholarship, eligible: true, reason: "Open to all applicants — sit the intake exam/interview to be assessed." }
        ];
    }
    /** Amount payable now: only automatic discounts apply at checkout (the server re-checks). */
    function compute(fee, { applyEarlyBird = earlyBirdOpen() } = {}) {
        const pct = applyEarlyBird ? cfg().earlybird : 0;
        const discount = Math.round(fee * pct / 100);
        return { fee, type: pct ? "earlybird" : null, pct, discount, payable: fee - discount };
    }
    return { get RULES() { return rules(); }, evaluate, compute, earlyBirdOpen, excellenceEligible, deadline };
})();

const Applications = (() => {
    const pad = (n) => String(n).padStart(5, "0");
    const all = () => DB.all("applications");
    const get = (id) => DB.get("applications", id);
    const fullName = (a) => [a.firstName, a.middleName, a.lastName].filter(Boolean).join(" ");
    const discountName = (t) => ({ earlybird: "Early Bird Discount", excellence: "Excellence Award", scholarship: "Performance Scholarship" }[t] || "None");
    const STATUSES = ["Pending", "Under Review", "Paid", "Accepted", "Enrolled", "Rejected"];

    function create(d) {
        const prog = Programmes.get(d.programmeId);
        const no = DB.next("app");
        const id = `TSCE/APP/${new Date().getFullYear()}/${pad(no)}`;
        const fees = Discounts.compute(prog.fee);
        const now = new Date().toISOString();
        const app = {
            id, firstName: d.firstName, middleName: d.middleName || "", lastName: d.lastName, gender: d.gender, dob: d.dob,
            phone: d.phone, email: d.email.toLowerCase(), address: d.address, state: d.state, lga: d.lga,
            qualification: d.qualification, institution: d.institution, gradYear: +d.gradYear || null,
            waecStatus: d.waecStatus, waecYear: +d.waecYear || null, numAs: +d.numAs || 0, resultFile: d.resultFile || null,
            programmeId: prog.id, schedule: d.schedule, intake: d.intake,
            fee: fees.fee, discountType: fees.type, discountPct: fees.pct, discountAmount: fees.discount, amountPayable: fees.payable,
            awardRequest: d.awardRequest && d.awardRequest !== "none" ? d.awardRequest : null,
            paymentStatus: "Unpaid", status: "Pending", txRef: null, studentId: null,
            portalPassword: d.password,          // DEMO ONLY — a real backend hashes this server-side
            createdAt: now, paidAt: null,
            history: [{ at: now, text: "Application submitted online" }]
        };
        DB.insert("applications", app);
        if (app.awardRequest) {
            const eligibleExcellence = Discounts.excellenceEligible(app);
            DB.insert("scholarships", {
                id: `SCH-${String(DB.all("scholarships").length + 1).padStart(4, "0")}`, applicationId: id, studentId: null,
                name: fullName(app), programmeId: prog.id, type: app.awardRequest, requestedPct: app.awardRequest === "excellence" ? 50 : 40,
                awardedPct: null, status: "Pending", createdAt: now, reviewedAt: null, reviewedBy: null, interviewScore: null,
                evidence: app.awardRequest === "excellence" ? `WAEC ${app.waecYear || "—"} — ${app.numAs} A's (declared${app.resultFile ? ", result uploaded" : ""})${eligibleExcellence ? "" : " · criteria not met"}` : "Intake exam to be scheduled"
            });
        }
        // An applicant login lets them come back to pay later.
        if (!DB.first("users", (u) => u.email === app.email)) DB.insert("users", { email: app.email, password: d.password, role: "applicant", name: fullName(app), applicationId: id });
        Notifications.push(app.email, "Application received", "Your application has been received.", "application");
        Notifications.push("staff", "New application", `${fullName(app)} applied for ${prog.name}.`, "application");
        return app;
    }

    /** Called after a verified successful payment. Activates the student account. */
    function markPaid(appId, payment, { silent = false } = {}) {
        const app = get(appId);
        if (!app) return null;
        const now = new Date().toISOString();
        const studentId = app.studentId || `TSCE/2026/${appId.split("/").pop()}`;
        const prog = Programmes.get(app.programmeId);
        const history = [...(app.history || []), { at: now, text: `Payment of ${UI.naira(payment.amount)} confirmed via Zainpay (${payment.ref})`, ok: true }, { at: now, text: `Student portal account activated (${studentId})`, ok: true }];
        // Already-approved applicants are enrolled the moment payment is verified.
        const newStatus = ["Pending", "Under Review"].includes(app.status) ? "Paid" : app.status === "Accepted" ? "Enrolled" : app.status;
        if (newStatus === "Enrolled" && app.status !== "Enrolled") history.push({ at: now, text: `Enrolled as ${studentId}`, ok: true });
        DB.update("applications", appId, { paymentStatus: "Paid", status: newStatus, paidAt: now, txRef: payment.ref, studentId, history, portalPassword: undefined });
        DB.update("payments", payment.ref, { studentId });

        if (!DB.get("students", studentId)) {
            const start = new Date(DB.settings().admissions?.cohortDate || TSCE_FLYER.startDate);
            const end = new Date(start); end.setDate(end.getDate() + prog.weeks * 7 - 3);
            DB.insert("students", {
                id: studentId, appId, userEmail: app.email, firstName: app.firstName, middleName: app.middleName, lastName: app.lastName, gender: app.gender,
                phone: app.phone, email: app.email, dob: app.dob, state: app.state, lga: app.lga, address: app.address,
                qualification: app.qualification, institution: app.institution, programmeId: app.programmeId, cohort: app.intake, schedule: app.schedule,
                startDate: start.toISOString(), endDate: end.toISOString(), instructor: prog.instructor, progress: 0, moduleProgress: prog.modules.map(() => 0),
                status: app.status === "Accepted" ? "Active" : "Admission Pending", paymentStatus: "Paid", amountPaid: payment.amount,
                discountType: app.discountType, discountPct: app.discountPct, certificateNo: `TSCE/CERT/2026/${appId.split("/").pop()}`,
                certificateStatus: "Not Issued", certificateIssuedAt: null, emergencyContact: "", createdAt: now
            });
        }
        const user = DB.first("users", (u) => u.email === app.email);
        const users = DB.all("users").filter((u) => u.email !== app.email);
        users.push({ email: app.email, password: user?.password || app.portalPassword || "student123", role: "student", name: fullName(app), studentId });
        DB.save("users", users);
        DB.update("scholarships", (DB.first("scholarships", (s) => s.applicationId === appId) || {}).id, { studentId });

        if (!silent) {
            Notifications.push(app.email, "Payment successful", `Your payment was successful. Ref: ${payment.ref}`, "payment");
            Notifications.push(app.email, "Welcome to TSCE", `Your class begins ${UI.dateLong(DB.settings().admissions?.cohortDate || TSCE_FLYER.startDate)}.`, "announcement");
        }
        Notifications.push("staff", "Payment received", `${fullName(app)} paid ${UI.naira(payment.amount)} for ${prog.name}.`, "payment");
        return get(appId);
    }

    function markPaymentFailed(appId, payment) {
        const app = get(appId);
        if (!app) return;
        DB.update("applications", appId, { paymentStatus: "Failed", history: [...app.history, { at: new Date().toISOString(), text: `Payment attempt failed (${payment.ref})` }] });
    }

    /** Staff lifecycle actions. */
    function setStatus(appId, status, note = "") {
        const app = get(appId);
        const now = new Date().toISOString();
        const text = { "Under Review": "Moved to review by Admissions Office", Accepted: "Application accepted", Rejected: "Application rejected", Enrolled: `Enrolled as ${app.studentId}` }[status] || `Status changed to ${status}`;
        const history = [...(app.history || []), { at: now, text: text + (note ? ` — ${note}` : ""), ok: ["Accepted", "Enrolled"].includes(status) }];
        let final = status;
        // Approving a paid applicant admits & enrols them in one step.
        if (status === "Accepted" && app.paymentStatus === "Paid") {
            final = "Enrolled";
            history.push({ at: now, text: `Enrolled as ${app.studentId}`, ok: true });
        }
        DB.update("applications", appId, { status: final, history });
        if (app.studentId) {
            if (final === "Enrolled") DB.update("students", app.studentId, { status: "Active" });
            if (final === "Rejected") DB.update("students", app.studentId, { status: "Withdrawn" });
        }
        const msgs = {
            "Under Review": "Your application is now under review by the Admissions Office.",
            Accepted: "Congratulations! Your application has been accepted. Complete payment to secure your seat.",
            Enrolled: `Congratulations! You have been admitted. Your class begins ${UI.dateLong(DB.settings().admissions?.cohortDate || TSCE_FLYER.startDate)}.`,
            Rejected: "We're sorry — your application was not successful this time." + (note ? ` Reason: ${note}` : "")
        };
        Notifications.push(app.email, `Application ${final.toLowerCase()}`, msgs[final] || `Your application status is now ${final}.`, "application");
        return get(appId);
    }

    function lifecycle(app) {
        const steps = ["Submitted", "Paid", "Review", "Accepted", "Enrolled"];
        const idx = app.status === "Enrolled" ? 5 : app.status === "Accepted" ? (app.paymentStatus === "Paid" ? 4 : 3) : app.status === "Under Review" ? 2 + (app.paymentStatus === "Paid" ? 0 : 0) : app.paymentStatus === "Paid" ? 2 : 1;
        const rejected = app.status === "Rejected";
        return `<div class="lifecycle">${steps.map((s, i) => {
            const done = i < idx && !(rejected && i >= 2);
            const cur = !rejected && i === idx;
            return `<div class="lc-step ${done ? "done" : cur ? "current" : ""} ${rejected && i === 2 ? "bad" : ""}"><div class="c">${done ? '<i class="fa-solid fa-check"></i>' : rejected && i === 2 ? '<i class="fa-solid fa-xmark"></i>' : i + 1}</div>${rejected && i === 2 ? "Rejected" : s}</div>`;
        }).join("")}</div>`;
    }

    function printHTML(app) {
        const prog = Programmes.get(app.programmeId);
        const row = (k, v) => `<tr><td>${k}</td><td>${UI.esc(v ?? "—")}</td></tr>`;
        return `<div class="receipt"><div class="receipt-head"><div class="flex">${UI.logoFull("receipt-logo")}<div><h3>${TSCE_FLYER.name}</h3><p>${TSCE_FLYER.address}</p></div></div><div style="text-align:right"><h3>APPLICATION FORM</h3><p class="mono">${UI.esc(app.id)}</p></div></div>
            <table>${row("Full name", fullName(app))}${row("Gender", app.gender)}${row("Date of birth", UI.date(app.dob))}${row("Phone", app.phone)}${row("Email", app.email)}${row("Address", app.address)}${row("State / LGA", `${app.state} / ${app.lga}`)}
            ${row("Highest qualification", app.qualification)}${row("Institution", app.institution)}${row("WAEC", app.waecStatus === "Available" ? `${app.waecYear} — ${app.numAs} A's` : app.waecStatus)}
            ${row("Programme", prog.name)}${row("Schedule", app.schedule)}${row("Intake", app.intake)}${row("Programme fee", UI.naira(app.fee))}${row("Discount", app.discountAmount ? `${discountName(app.discountType)} (−${UI.naira(app.discountAmount)})` : "None")}
            ${row("Amount paid", app.paymentStatus === "Paid" ? UI.naira(app.amountPayable) : "Unpaid")}${row("Transaction ref.", app.txRef)}${row("Status", app.status)}${row("Submitted", UI.dateTime(app.createdAt))}</table>
            <p class="small muted mt-3">Printed from the TSCE Digital Platform on ${UI.dateTime(new Date())}.</p></div>`;
    }

    /* Staff detail drawer */
    function openDetail(id, onChange = () => { }) {
        const a = get(id);
        if (!a) return UI.toast("Application not found", "", "error");
        const prog = Programmes.get(a.programmeId);
        const sch = DB.first("scholarships", (s) => s.applicationId === a.id);
        const kv = (k, v, full) => `<div class="${full ? "full" : ""}"><small>${k}</small><strong>${v}</strong></div>`;
        const acts = [];
        if (["Pending", "Paid"].includes(a.status)) acts.push(`<button class="btn btn-outline" data-act="Under Review"><i class="fa-solid fa-magnifying-glass"></i> Move to review</button>`);
        if (!["Accepted", "Enrolled", "Rejected"].includes(a.status)) acts.push(`<button class="btn btn-soft-danger" data-act="Rejected"><i class="fa-solid fa-xmark"></i> Reject</button>`, `<button class="btn btn-success" data-act="Accepted"><i class="fa-solid fa-check"></i> ${a.paymentStatus === "Paid" ? "Approve & enrol" : "Approve"}</button>`);
        if (a.status === "Accepted" && a.paymentStatus !== "Paid") acts.push(`<button class="btn btn-outline" data-act="remind"><i class="fa-regular fa-bell"></i> Payment reminder</button>`);
        if (a.status === "Enrolled" && a.studentId) acts.push(`<a class="btn btn-primary" href="students.html?id=${encodeURIComponent(a.studentId)}"><i class="fa-solid fa-user-graduate"></i> Student record</a>`);
        const d = UI.drawer({
            title: UI.esc(fullName(a)), subtitle: `<span class="mono">${UI.esc(a.id)}</span> · ${UI.badge(a.status)} ${UI.badge(a.paymentStatus)}`,
            body: `${lifecycle(a)}
                <div class="dr-section"><h4>Programme & fees</h4><div class="kv">
                    ${kv("Programme", UI.esc(prog.name), true)}${kv("Schedule", UI.esc(a.schedule))}${kv("Intake", UI.esc(a.intake))}
                    ${kv("Programme fee", UI.naira(a.fee))}${kv("Discount", a.discountAmount ? `${discountName(a.discountType)} (−${UI.naira(a.discountAmount)})` : "None")}
                    ${kv("Amount payable", `<span style="font-family:var(--font-head);font-size:1.1rem">${UI.naira(a.amountPayable)}</span>`)}${kv("Transaction", a.txRef ? `<a href="payments.html?ref=${encodeURIComponent(a.txRef)}" class="mono">${UI.esc(a.txRef)}</a>` : "—")}
                    ${sch ? kv("Award request", `${discountName(sch.type)} · ${UI.badge(sch.status)} <a href="scholarships.html" class="small">Review →</a>`, true) : ""}
                </div></div>
                <div class="dr-section"><h4>Personal information</h4><div class="kv">
                    ${kv("Gender", a.gender)}${kv("Date of birth", UI.date(a.dob))}${kv("Phone", `<a href="tel:${UI.esc(a.phone)}">${UI.esc(a.phone)}</a>`)}${kv("Email", `<a href="mailto:${UI.esc(a.email)}">${UI.esc(a.email)}</a>`)}
                    ${kv("Address", UI.esc(a.address), true)}${kv("State", UI.esc(a.state))}${kv("LGA", UI.esc(a.lga))}</div></div>
                <div class="dr-section"><h4>Education</h4><div class="kv">
                    ${kv("Highest qualification", UI.esc(a.qualification))}${kv("Graduation year", a.gradYear || "—")}${kv("Institution", UI.esc(a.institution), true)}
                    ${kv("WAEC/NECO", UI.esc(a.waecStatus))}${kv("Result", a.waecStatus === "Available" ? `${a.waecYear} · ${a.numAs} A's` : "—")}
                    ${kv("Result document", a.resultFile ? `<i class="fa-regular fa-file-pdf" style="color:var(--danger)"></i> ${UI.esc(a.resultFile)}` : `<span class="muted">Not uploaded</span>`, true)}</div></div>
                <div class="dr-section"><h4>Activity</h4><ul class="history">${[...(a.history || [])].reverse().map((h) => `<li class="${h.ok ? "ok" : ""}"><strong>${UI.esc(h.text)}</strong><small>${UI.dateTime(h.at)}</small></li>`).join("")}</ul></div>`,
            footer: `<button class="btn btn-ghost" id="adPrint"><i class="fa-solid fa-print"></i></button>` + acts.join("")
        });
        UI.$("#adPrint", d.el).onclick = () => UI.printHTML(`Application ${a.id}`, printHTML(a));
        UI.$$("[data-act]", d.el).forEach((b) => b.onclick = async () => {
            const act = b.dataset.act;
            if (act === "remind") { Notifications.push(a.email, "Complete your payment", `Your admission is confirmed. Pay ${UI.naira(a.amountPayable)} to secure your seat.`, "payment"); UI.toast("Reminder sent", `Email + SMS to ${a.firstName} (simulated).`, "success"); return; }
            let note = "";
            if (act === "Rejected") {
                const ok = await UI.confirm({ title: "Reject this application?", message: `${UI.esc(fullName(a))} will be notified.${a.paymentStatus === "Paid" ? " Their payment will be refunded." : ""}`, confirmText: "Reject application", tone: "danger", icon: "fa-user-xmark" });
                if (!ok) return;
                note = "Did not meet admission requirements";
                if (a.txRef && a.paymentStatus === "Paid") DB.update("payments", a.txRef, { status: "REFUNDED", refundedAt: new Date().toISOString() });
            }
            const upd = setStatus(a.id, act, note);
            d.close();
            UI.toast(`Application ${upd.status.toLowerCase()}`, `${fullName(a)} — ${a.id}`, act === "Rejected" ? "warning" : "success");
            if (upd.status === "Enrolled") setTimeout(() => UI.toast("Student enrolled", `${a.firstName} can now access the full student portal.`, "success"), 400);
            onChange();
        });
    }

    return { all, get, fullName, discountName, STATUSES, create, markPaid, markPaymentFailed, setStatus, lifecycle, printHTML, openDetail };
})();

/* ---------------- Public: Application wizard ---------------- */
Pages["application"] = function () {
    const STATES = ["Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue", "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu", "FCT", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara"];
    const LGAS = { Kaduna: ["Zaria", "Sabon Gari", "Giwa", "Igabi", "Kaduna North", "Kaduna South", "Chikun", "Soba", "Makarfi", "Kudan", "Ikara", "Kubau"], Kano: ["Nassarawa", "Fagge", "Tarauni", "Gwale", "Dala", "Kano Municipal"], Katsina: ["Katsina", "Funtua", "Daura", "Malumfashi"], FCT: ["AMAC", "Bwari", "Gwagwalada", "Kuje"], Sokoto: ["Sokoto North", "Sokoto South", "Wamakko"], Zamfara: ["Gusau", "Kaura Namoda"], Niger: ["Minna", "Bida", "Suleja"], Plateau: ["Jos North", "Jos South"], Bauchi: ["Bauchi", "Azare"], Lagos: ["Ikeja", "Eti-Osa", "Surulere", "Alimosho"] };
    const MAX_FILE = 5 * 1024 * 1024;
    const adm = Site.settings?.admissions;
    const user = Auth.current();
    const form = UI.$("#appForm");
    const panels = UI.$$(".wpanel", form);
    const stepEls = UI.$$(".wstep");
    let step = 0;
    let programmeId = UI.param("programme") || null;
    let waecFile = null;                 // the File object; can't be saved in a draft
    const TOTAL = panels.length;

    if (!Site.ready) {
        UI.$("#wizardRoot").innerHTML = `<div class="card">${UI.empty({ icon: "fa-plug-circle-xmark", title: "We couldn't reach the TSCE server", text: "Check your internet connection and reload the page.", action: `<button class="btn btn-primary" onclick="location.reload()">Reload</button>` })}</div>`;
        return;
    }
    if (!adm.open) {
        UI.$("#wizardRoot").innerHTML = `<div class="card">${UI.empty({ icon: "fa-door-closed", title: "Applications are currently closed", text: UI.esc(adm.closedMessage), action: `<a class="btn btn-primary" href="contact.html">Contact admissions</a>` })}</div>`;
        return;
    }
    if (user && ["staff", "admin"].includes(user.role)) {
        UI.$("#wizardRoot").innerHTML = `<div class="card">${UI.empty({ icon: "fa-id-badge", title: "You're signed in with a staff account", text: "Staff accounts can't apply. Sign out to apply with a personal email.", action: `<button class="btn btn-primary" onclick="Auth.logout()">Sign out</button>` })}</div>`;
        return;
    }

    // Drafts live in sessionStorage: they survive a reload but not closing the tab,
    // so personal details aren't left behind on shared (e.g. cybercafé) computers.
    const drafts = {
        get() { try { return JSON.parse(sessionStorage.getItem("tsce_appDraft")); } catch (e) { return null; } },
        set(v) { try { sessionStorage.setItem("tsce_appDraft", JSON.stringify(v)); } catch (e) { /* ignore */ } },
        clear() { try { sessionStorage.removeItem("tsce_appDraft"); } catch (e) { /* ignore */ } }
    };

    // Populate selects
    UI.$("#a_state").innerHTML = `<option value="">Select state</option>` + STATES.map((s) => `<option>${s}</option>`).join("");
    UI.$("#a_state").addEventListener("change", () => { UI.$("#lgaList").innerHTML = (LGAS[UI.$("#a_state").value] || []).map((l) => `<option value="${l}">`).join(""); });
    UI.$("#a_intake").innerHTML = `<option value="${UI.esc(adm.intake)}">${UI.esc(adm.intake)} — starts ${UI.date(Site.day(adm.cohortDate))}</option>`;

    // Signed-in applicants apply as themselves: email fixed, no password needed.
    if (user) {
        UI.$("#a_email").value = user.email;
        UI.$("#a_email").readOnly = true;
        UI.$("#a_email").closest(".field").querySelector(".hint").textContent = `Signed in as ${user.email}.`;
        UI.$$("#a_password, #a_password2").forEach((i) => { i.required = false; i.closest(".field").classList.add("hidden"); });
    }

    // Programme picker
    function renderProgrammes() {
        UI.$("#progPicker").innerHTML = Programmes.active().map((p) => {
            const s = Programmes.seats(p);
            return `<button type="button" class="prog-option ${p.id === programmeId ? "selected" : ""} ${s.available === 0 ? "disabled" : ""}" data-pid="${p.id}" style="--pc:${p.color}" aria-pressed="${p.id === programmeId}" ${s.available === 0 ? "disabled" : ""}>
                <span class="icon-tile"><i class="fa-solid ${p.icon}"></i></span><div><strong>${UI.esc(p.name)}</strong><small>${p.weeks} weeks · ${s.available ? s.available + " seats left" : "Full"}</small></div><span class="po-fee">${UI.naira(p.fee)}</span></button>`;
        }).join("");
        UI.$$(".prog-option").forEach((b) => b.addEventListener("click", () => { programmeId = b.dataset.pid; renderProgrammes(); updateProgrammeSummary(); saveDraft(); UI.fieldError(UI.$("#a_programme"), ""); }));
    }
    function updateProgrammeSummary() {
        const p = programmeId && Programmes.get(programmeId);
        UI.$("#a_programme").value = programmeId || "";
        const sched = UI.$("#a_schedule");
        const current = sched.value;
        sched.innerHTML = `<option value="">Select schedule</option>` + (p ? p.schedules.map((x) => `<option ${x === current ? "selected" : ""}>${UI.esc(x)}</option>`).join("") : "");
        UI.$("#progFee").innerHTML = p ? `<div class="fee-box"><div class="fee-head"><div class="flex"><span class="icon-tile" style="background:${p.color};color:#fff;width:40px;height:40px"><i class="fa-solid ${p.icon}"></i></span><div><strong style="font-family:var(--font-head)">${UI.esc(p.name)}</strong><div class="small muted">${p.weeks} weeks · ${p.modules.length} modules${p.instructor ? " · " + UI.esc(p.instructor) : ""}</div></div></div><button type="button" class="link-btn small" id="viewProg">Details</button></div>
            <div class="fee-row total"><span>Programme Fee</span><span>${UI.naira(p.fee)}</span></div></div>` : `<div class="alert"><i class="fa-solid fa-hand-pointer"></i><p>Select a programme to see the fee.</p></div>`;
        UI.$("#viewProg")?.addEventListener("click", () => Programmes.openDetail(p.id));
    }

    // WAEC conditional fields + excellence hint
    function waecUI() {
        const avail = UI.$("#a_waec").value === "Available";
        UI.$$(".waec-dep").forEach((e) => { e.classList.toggle("hidden", !avail); UI.$$("input", e).forEach((i) => i.required = avail && i.dataset.req === "1"); });
        const d = { waecStatus: UI.$("#a_waec").value, waecYear: UI.$("#a_waecYear").value, numAs: UI.$("#a_numAs").value };
        UI.$("#excHint").innerHTML = Discounts.excellenceEligible(d) ? `<div class="alert success"><i class="fa-solid fa-award"></i><p><b>Great news!</b> Your WAEC result may qualify you for the <b>${Discounts.RULES.excellence.pct}% Excellence Award</b>. You can request it on the review step.</p></div>` : "";
    }
    ["#a_waec", "#a_waecYear", "#a_numAs"].forEach((s) => UI.$(s).addEventListener("input", waecUI));

    // Result upload (sent with the application; checked again on the server)
    const up = UI.$("#uploadBox"), file = UI.$("#a_file");
    const upIdle = up.innerHTML;
    up.addEventListener("click", () => file.click());
    up.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); file.click(); } });
    ["dragover", "dragenter"].forEach((ev) => up.addEventListener(ev, (e) => { e.preventDefault(); up.classList.add("dragover"); }));
    ["dragleave", "drop"].forEach((ev) => up.addEventListener(ev, (e) => { e.preventDefault(); up.classList.remove("dragover"); if (ev === "drop" && e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]); }));
    file.addEventListener("change", () => file.files[0] && setFile(file.files[0]));
    function setFile(f) {
        const ok = /\.(pdf|jpe?g|png)$/i.test(f.name);
        if (!ok || f.size > MAX_FILE) {
            waecFile = null; up.classList.remove("done"); up.innerHTML = upIdle;
            UI.toast("File not accepted", ok ? "The file is larger than 5 MB." : "Upload a PDF, JPG or PNG file.", "warning");
            return;
        }
        waecFile = f;
        up.classList.add("done");
        up.innerHTML = `<i class="fa-solid fa-file-circle-check"></i><div><b>${UI.esc(f.name)}</b></div><div class="hint">${(f.size / 1024 / 1024).toFixed(1)} MB · click to replace</div>`;
    }

    // Password strength
    UI.$("#a_password").addEventListener("input", (e) => {
        const v = e.target.value; let sc = 0;
        if (v.length >= 8) sc++; if (/[A-Z]/.test(v) && /[a-z]/.test(v)) sc++; if (/\d/.test(v)) sc++; if (/[^A-Za-z0-9]/.test(v) || v.length >= 12) sc++;
        UI.$$(".pw-meter span").forEach((s, i) => s.style.background = i < sc ? ["#DC2F45", "#F5B400", "#0EA5E9", "#12A150"][sc - 1] : "");
    });

    // Draft autosave (never the password or the file)
    function data() { return { ...UI.formData(form), programmeId }; }
    function saveDraft() { const d = data(); delete d.password; delete d.password2; drafts.set({ ...d, step }); UI.$("#draftNote").textContent = "Draft saved " + new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }); }
    function loadDraft() {
        const d = drafts.get();
        if (!d) return;
        Object.entries(d).forEach(([k, v]) => { const el = form.elements[k]; if (!el || k === "step" || (k === "email" && user)) return; if (el instanceof RadioNodeList) { UI.$$(`input[name="${k}"]`, form).forEach((r) => r.checked = r.value === v); } else if (el.type !== "file") el.value = v; });
        if (!programmeId && d.programmeId) programmeId = d.programmeId;
        UI.$("#a_state").dispatchEvent(new Event("change"));
        UI.$("#draftNote").textContent = "Draft restored";
    }
    form.addEventListener("input", UI.debounce(saveDraft, 500));

    // Review step
    function renderReview() {
        const d = data(); const p = Programmes.get(programmeId);
        const ev = Discounts.evaluate(d);
        const fees = Discounts.compute(p.fee);
        const selected = d.awardRequest || "none";
        UI.$("#discountList").innerHTML = ev.map((r) => {
            const isEB = r.id === "earlybird";
            const cls = isEB ? (r.eligible ? "eligible applied" : "ineligible") : r.eligible ? "eligible" : "ineligible";
            const status = isEB ? (r.eligible ? UI.badge("Applied") : UI.badge("Closed")) : r.eligible ? UI.badge(r.id === "excellence" ? "Eligible" : "Requested", "") : UI.badge("Not eligible");
            const ctrl = isEB ? "" : `<label class="check mt-1" style="font-size:.84rem"><input type="radio" name="awardRequest" value="${r.id}" ${selected === r.id ? "checked" : ""} ${r.eligible ? "" : "disabled"}> Request ${r.name.toLowerCase()} review</label>`;
            return `<div class="discount-card ${cls}"><div class="pct-pill">${r.upTo ? "≤" : ""}${r.pct}%</div><div style="flex:1"><div class="flex between" style="align-items:flex-start"><h4>${r.name}</h4>${isEB || r.id === "excellence" ? status : ""}</div><p>${r.condition}</p><p class="mt-1" style="color:var(--text-2)">${r.reason}</p>${ctrl}</div></div>`;
        }).join("") + `<label class="check" style="font-size:.84rem;padding:4px 4px 0"><input type="radio" name="awardRequest" value="none" ${selected === "none" ? "checked" : ""}> Don't request an award review</label>`;

        UI.$("#feeCalc").innerHTML = `<div class="fee-box"><div class="fee-head"><strong style="font-family:var(--font-head)">Fee calculation</strong><span class="badge badge-primary no-dot">${UI.esc(d.intake)}</span></div>
            <div class="fee-row"><span>Programme Fee</span><span>${UI.naira(fees.fee)}</span></div>
            ${fees.discount ? `<div class="fee-row"><span>Early Bird Discount (${fees.pct}%)</span><span class="neg">−${UI.naira(fees.discount)}</span></div>` : `<div class="fee-row"><span>Discount</span><span class="muted">—</span></div>`}
            <div class="fee-row total"><span>Amount Payable</span><span>${UI.naira(fees.payable)}</span></div></div>
            <p class="hint mt-1"><i class="fa-solid fa-circle-info"></i> Discounts don't stack. If an Excellence Award or Scholarship is approved, it replaces the early-bird discount and the difference is refunded.</p>`;

        const r = (k, v) => `<div><small>${k}</small><strong>${UI.esc(v || "—")}</strong></div>`;
        UI.$("#reviewGrid").innerHTML = r("Full name", [d.firstName, d.middleName, d.lastName].filter(Boolean).join(" ")) + r("Email", d.email) + r("Phone", d.phone) + r("Gender · DOB", `${d.gender} · ${UI.date(d.dob)}`) + r("State · LGA", `${d.state} · ${d.lga}`) + r("Qualification", `${d.qualification} — ${d.institution}`) + r("WAEC/NECO", d.waecStatus === "Available" ? `${d.waecYear} · ${d.numAs} A's${waecFile ? " · result attached" : ""}` : d.waecStatus) + r("Programme", p.name) + r("Schedule", d.schedule) + r("Intake", d.intake);
        UI.$("#payBtnAmt").textContent = UI.naira(fees.payable);
        UI.$$('input[name="awardRequest"]').forEach((i) => i.addEventListener("change", saveDraft));
    }

    // Navigation
    function go(n, { scroll = true } = {}) {
        step = Math.max(0, Math.min(TOTAL - 1, n));
        panels.forEach((p, i) => p.classList.toggle("active", i === step));
        stepEls.forEach((s, i) => { s.classList.toggle("active", i === step); s.classList.toggle("done", i < step); s.querySelector(".dot").innerHTML = i < step ? '<i class="fa-solid fa-check"></i>' : i + 1; if (i === step) s.setAttribute("aria-current", "step"); else s.removeAttribute("aria-current"); });
        UI.$("#wProgress").style.width = ((step + 1) / (TOTAL + 1) * 100) + "%";
        UI.$("#wTitle").textContent = panels[step].dataset.title;
        UI.$("#wSub").textContent = panels[step].dataset.sub;
        UI.$("#wStepNo").textContent = `Step ${step + 1} of ${TOTAL + 1}`;
        UI.$("#prevBtn").style.visibility = step === 0 ? "hidden" : "visible";
        UI.$("#nextBtn").classList.toggle("hidden", step === TOTAL - 1);
        UI.$("#submitBtn").classList.toggle("hidden", step !== TOTAL - 1);
        if (step === 2) { renderProgrammes(); updateProgrammeSummary(); }
        if (step === TOTAL - 1) renderReview();
        if (scroll) window.scrollTo({ top: UI.$("#wizardRoot").offsetTop - 90, behavior: "smooth" });
        saveDraft();
    }
    function validStep() {
        if (step === 2 && !programmeId) { UI.fieldError(UI.$("#a_programme"), "Please select a programme."); UI.toast("Select a programme", "Choose the programme you want to apply for.", "warning"); return false; }
        return UI.validate(panels[step]);
    }
    UI.$("#nextBtn").addEventListener("click", () => { if (validStep()) go(step + 1); });
    UI.$("#prevBtn").addEventListener("click", () => go(step - 1));
    stepEls.forEach((s, i) => s.addEventListener("click", () => { if (i < step) go(i); }));
    UI.$$("[data-goto]").forEach((b) => b.addEventListener("click", () => go(+b.dataset.goto)));
    UI.liveValidate(form);

    /** Server field errors → highlight them and jump to the first step that has one. */
    function showServerErrors(err) {
        const fields = Object.keys(err.fields || {});
        API.showFieldErrors(form, err);
        if (err.fields?.programmeId) UI.fieldError(UI.$("#a_programme"), [].concat(err.fields.programmeId)[0]);
        if (err.fields?.resultFile) UI.toast("WAEC result upload", [].concat(err.fields.resultFile)[0], "warning");
        const stepOf = (name) => panels.findIndex((p) => name === "programmeId" ? p.contains(UI.$("#a_programme")) : name === "resultFile" ? p.contains(up) : p.querySelector(`[name="${CSS.escape(name)}"]`));
        const first = fields.map(stepOf).filter((i) => i >= 0).sort((a, b) => a - b)[0];
        if (first !== undefined && first !== step) go(first);
    }

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        if (!validStep()) return;
        const btn = UI.$("#submitBtn");
        btn.disabled = true; btn.innerHTML = `<span class="spinner"></span> Submitting application…`;
        const d = data();
        const fd = new FormData();
        ["firstName", "middleName", "lastName", "gender", "dob", "phone", "email", "address", "state", "lga", "qualification", "institution", "gradYear", "waecStatus", "waecYear", "numAs", "schedule"].forEach((k) => fd.append(k, d[k] ?? ""));
        fd.append("programmeId", programmeId);
        fd.append("awardRequest", d.awardRequest || "none");
        if (!user) fd.append("password", UI.$("#a_password").value);
        fd.append("declare", UI.$("#a_declare").checked ? "true" : "false");
        if (waecFile && d.waecStatus === "Available") fd.append("resultFile", waecFile);
        try {
            const res = await API.post("applications", fd);
            drafts.clear();
            UI.toast("Application submitted", `${res.application.id} — proceeding to secure payment`, "success");
            setTimeout(() => location.href = `payment.html?app=${encodeURIComponent(res.application.id)}`, 500);
            return;
        } catch (err) {
            if (err.code === "duplicate_application") {
                const no = err.data?.extra?.applicationId;
                UI.modal({
                    title: "You've already applied", size: "sm", body: `<p>${UI.esc(err.message)}</p><p class="muted small">Sign in with the same email to continue, or pay for your existing application.</p>`,
                    footer: `<button class="btn btn-ghost" data-close>Close</button><a class="btn btn-primary" href="payment.html?app=${encodeURIComponent(no || "")}">Continue to payment</a>`
                });
            } else if (Object.keys(err.fields || {}).length) {
                showServerErrors(err);
                UI.toast("Please check your application", err.message, "warning");
            } else {
                UI.toast("Couldn't submit application", err.message, "error");
            }
        }
        btn.disabled = false; btn.innerHTML = `Proceed to Payment · <span id="payBtnAmt"></span>`;
        if (step === TOTAL - 1) renderReview();
    });

    loadDraft();
    waecUI();
    const d0 = drafts.get();
    if (UI.param("programme")) programmeId = UI.param("programme");
    let startAt = !UI.param("programme") && d0?.step ? d0.step : 0;
    if (startAt >= 2 && !programmeId) startAt = 2;
    go(startAt, { scroll: false });
};

/* ---------------- Staff: Applications ---------------- */
Pages["staff-applications"] = function (view) {
    let status = UI.param("status") || "";
    view.innerHTML = `
        <div class="view-head"><div><h2>Applications</h2><p>Review, approve and enrol applicants for the ${UI.esc(DB.settings().admissions?.intake || "current intake")}.</p></div>
            <div class="actions"><button class="btn btn-outline" id="appExport"><i class="fa-solid fa-file-csv"></i> Export CSV</button><a class="btn btn-primary" href="../application.html" target="_blank" rel="noopener"><i class="fa-solid fa-plus"></i> New application</a></div></div>
        <div class="stat-chips" id="statusChips" role="tablist" aria-label="Filter by status"></div>
        <div class="panel">
            <div class="table-tools">
                <div class="input-icon"><i class="fa-solid fa-magnifying-glass"></i><input class="input" id="aSearch" placeholder="Search name, ID, email, phone…" aria-label="Search applications"></div>
                <select class="select" id="aProg" aria-label="Programme"><option value="">All programmes</option>${Programmes.all().map((p) => `<option value="${p.id}">${UI.esc(p.name)}</option>`).join("")}</select>
                <select class="select" id="aPay" aria-label="Payment"><option value="">Any payment</option><option>Paid</option><option>Unpaid</option><option>Pending</option><option>Failed</option></select>
                <input type="date" class="input" id="aFrom" aria-label="From date" style="width:auto"><input type="date" class="input" id="aTo" aria-label="To date" style="width:auto">
                <button class="btn btn-ghost btn-sm" id="aClear"><i class="fa-solid fa-rotate-left"></i> Reset</button>
            </div>
            <div id="appTable"></div></div>`;

    function chips() {
        const apps = Applications.all();
        UI.$("#statusChips").innerHTML = [["", "All", apps.length], ...Applications.STATUSES.map((s) => [s, s, apps.filter((a) => a.status === s).length])]
            .map(([v, l, n]) => `<button class="stat-chip ${status === v ? "active" : ""}" data-st="${v}" role="tab" aria-selected="${status === v}">${l} <b>${n}</b></button>`).join("");
        UI.$$("#statusChips .stat-chip").forEach((c) => c.onclick = () => { status = c.dataset.st; refresh(); });
    }
    const table = UI.dataTable("#appTable", {
        pageSize: 10, onRowClick: (id) => Applications.openDetail(id, refresh),
        onRender: (el) => UI.$$("[data-quick]", el).forEach((b) => b.onclick = (e) => {
            e.stopPropagation();
            const a = Applications.setStatus(b.dataset.quick, "Accepted");
            UI.toast(`Application ${a.status.toLowerCase()}`, Applications.fullName(a), "success"); refresh();
        }),
        empty: { icon: "fa-file-circle-question", title: "No applications found.", text: "No applications match the selected filters.", action: `<button class="btn btn-soft" onclick="document.getElementById('aClear').click()">Clear filters</button>` },
        columns: [
            { key: "id", label: "Application ID", render: (a) => `<span class="ref">${UI.esc(a.id)}</span>` },
            { key: "lastName", label: "Applicant", sortValue: (a) => a.firstName, render: (a) => `<div class="person">${UI.avatar(Applications.fullName(a), "sm")}<div><strong>${UI.esc(a.firstName + " " + a.lastName)}</strong><small>${UI.esc(a.email)}</small></div></div>` },
            { key: "programmeId", label: "Programme", sortValue: (a) => Programmes.name(a.programmeId), render: (a) => `<span class="small">${UI.esc(Programmes.name(a.programmeId))}</span>` },
            { key: "createdAt", label: "Date", render: (a) => `<span class="small">${UI.date(a.createdAt)}</span>` },
            { key: "paymentStatus", label: "Payment", render: (a) => UI.badge(a.paymentStatus) },
            { key: "awardRequest", label: "Scholarship", render: (a) => { const s = DB.first("scholarships", (x) => x.applicationId === a.id); return s ? `<span class="small">${Applications.discountName(s.type).replace("Performance ", "")}</span><br>${UI.badge(s.status)}` : a.discountType === "earlybird" ? `<span class="small muted">Early bird</span>` : `<span class="muted">—</span>`; } },
            { key: "status", label: "Status", render: (a) => UI.badge(a.status) },
            { key: "", label: "Action", sortable: false, render: (a) => `<div class="row-actions">${!["Accepted", "Enrolled", "Rejected"].includes(a.status) ? `<button class="icon-btn success" data-quick="${UI.esc(a.id)}" title="Approve" aria-label="Approve ${UI.esc(a.firstName)}"><i class="fa-solid fa-check"></i></button>` : ""}<button class="btn btn-xs btn-soft">View</button></div>` }
        ],
        mobile: (a) => `<div class="m-row"><strong>${UI.esc(a.firstName + " " + a.lastName)}</strong>${UI.badge(a.status)}</div><div class="m-row"><span class="ref">${UI.esc(a.id)}</span>${UI.badge(a.paymentStatus)}</div><div class="m-row"><span>${UI.esc(Programmes.name(a.programmeId))}</span><span>${UI.date(a.createdAt)}</span></div>`
    });
    function refresh() {
        const q = UI.$("#aSearch").value.toLowerCase(), pr = UI.$("#aProg").value, pay = UI.$("#aPay").value, from = UI.$("#aFrom").value, to = UI.$("#aTo").value;
        const list = Applications.all().filter((a) => (!status || a.status === status) && (!pr || a.programmeId === pr) && (!pay || a.paymentStatus === pay)
            && (!from || a.createdAt.slice(0, 10) >= from) && (!to || a.createdAt.slice(0, 10) <= to)
            && [a.id, a.firstName, a.lastName, a.email, a.phone].join(" ").toLowerCase().includes(q))
            .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
        table.update(list, { resetPage: false });
        chips();
        Dashboard.refreshSidebarCounts && Dashboard.refreshSidebarCounts();
    }
    ["#aSearch"].forEach((s) => UI.$(s).addEventListener("input", UI.debounce(refresh, 150)));
    ["#aProg", "#aPay", "#aFrom", "#aTo"].forEach((s) => UI.$(s).addEventListener("change", refresh));
    UI.$("#aClear").onclick = () => { ["#aSearch", "#aProg", "#aPay", "#aFrom", "#aTo"].forEach((s) => UI.$(s).value = ""); status = ""; refresh(); };
    UI.$("#appExport").onclick = () => UI.downloadCSV("tsce-applications.csv", Applications.all().map((a) => ({ ApplicationID: a.id, Applicant: Applications.fullName(a), Email: a.email, Phone: a.phone, Programme: Programmes.name(a.programmeId), Intake: a.intake, Date: UI.date(a.createdAt), Fee: a.fee, Discount: a.discountAmount, Payable: a.amountPayable, Payment: a.paymentStatus, Status: a.status, TransactionRef: a.txRef || "" })));
    refresh();
    const open = UI.param("id"); if (open) Applications.openDetail(open, refresh);
};

/* ---------------- Staff: Scholarships & discounts ---------------- */
Pages["staff-scholarships"] = function (view) {
    let tab = "Pending";
    view.innerHTML = `
        <div class="view-head"><div><h2>Scholarships & Discounts</h2><p>Review award requests, verify WAEC results, assign scholarship percentages and track discount history.</p></div>
            <div class="actions"><button class="btn btn-outline" id="schExport"><i class="fa-solid fa-file-csv"></i> Export</button></div></div>
        <div class="grid grid-3 mb-3" id="schTypes"></div>
        <div class="panel"><div class="panel-head"><div class="tabs" id="schTabs" role="tablist"></div><div class="input-icon" style="width:260px;max-width:100%"><i class="fa-solid fa-magnifying-glass"></i><input class="input" id="schSearch" placeholder="Search…" aria-label="Search scholarships" style="height:40px"></div></div><div id="schTable"></div></div>`;

    function types() {
        const S = DB.all("scholarships"), A = Applications.all();
        const exc = S.filter((s) => s.type === "excellence"), sch = S.filter((s) => s.type === "scholarship"), eb = A.filter((a) => a.discountType === "earlybird");
        const val = A.reduce((t, a) => t + (a.paymentStatus === "Paid" ? a.discountAmount || 0 : 0), 0);
        UI.$("#schTypes").innerHTML = `
            <div class="offer-card"><span class="badge badge-gold ribbon">Verification</span><div class="pct"><small>Excellence Award</small>50<sup>%</sup></div><p>WAEC 2020-date with 5 A's or more.</p><div class="flex mt-2 small"><b>${exc.filter((s) => s.status === "Approved").length}</b> approved · <b>${exc.filter((s) => s.status === "Pending").length}</b> pending</div></div>
            <div class="offer-card featured"><span class="badge badge-primary ribbon" style="background:rgba(255,255,255,.15);color:#fff">Assessment</span><div class="pct"><small>Performance Scholarship</small>≤40<sup>%</sup></div><p>Based on intake exam / interview performance.</p><div class="flex mt-2 small" style="color:#DCE6FF"><b>${sch.filter((s) => s.status === "Approved").length}</b> approved · <b>${sch.filter((s) => s.status === "Pending").length}</b> pending</div><span class="deco"></span></div>
            <div class="offer-card"><span class="badge badge-success ribbon">Automatic</span><div class="pct"><small>Early Bird</small>15<sup>%</sup></div><p>Applied automatically for payment before 1 Oct 2026.</p><div class="flex mt-2 small"><b>${eb.length}</b> beneficiaries · <b>${UI.naira(val, { compact: true })}</b> total discounts</div></div>`;
    }
    function tabs() {
        const S = DB.all("scholarships");
        const defs = [["Pending", S.filter((s) => s.status === "Pending").length], ["Approved", S.filter((s) => s.status === "Approved").length], ["Rejected", S.filter((s) => s.status === "Rejected").length], ["Early Bird", Applications.all().filter((a) => a.discountType === "earlybird").length], ["History", S.length]];
        UI.$("#schTabs").innerHTML = defs.map(([t, n]) => `<button class="tab ${tab === t ? "active" : ""}" data-t="${t}" role="tab" aria-selected="${tab === t}">${t} <span class="badge badge-neutral no-dot" style="height:20px">${n}</span></button>`).join("");
        UI.$$("#schTabs .tab").forEach((b) => b.onclick = () => { tab = b.dataset.t; refresh(); });
    }
    const schCols = [
        { key: "name", label: "Applicant", render: (s) => `<div class="person">${UI.avatar(s.name, "sm")}<div><strong>${UI.esc(s.name)}</strong><small class="mono">${UI.esc(s.applicationId)}</small></div></div>` },
        { key: "programmeId", label: "Programme", render: (s) => `<span class="small">${UI.esc(Programmes.name(s.programmeId))}</span>` },
        { key: "type", label: "Type", render: (s) => `<span class="badge ${s.type === "excellence" ? "badge-gold" : "badge-primary"} no-dot">${Applications.discountName(s.type)}</span>` },
        { key: "evidence", label: "Evidence", render: (s) => `<span class="small">${UI.esc(s.evidence)}</span>${s.interviewScore ? `<div class="small muted">Interview: <b>${s.interviewScore}%</b></div>` : ""}` },
        { key: "awardedPct", label: "Award", cls: "num", render: (s) => s.awardedPct ? `<b>${s.awardedPct}%</b>` : `<span class="muted">req. ${s.requestedPct}%</span>` },
        { key: "status", label: "Status", render: (s) => UI.badge(s.status) + (s.reviewedAt ? `<div class="small muted">${UI.date(s.reviewedAt)}</div>` : "") },
        { key: "", label: "", sortable: false, render: (s) => s.status === "Pending" ? `<button class="btn btn-xs btn-primary">Review</button>` : `<button class="btn btn-xs btn-soft">View</button>` }
    ];
    const ebCols = [
        { key: "lastName", label: "Applicant", render: (a) => `<div class="person">${UI.avatar(Applications.fullName(a), "sm")}<div><strong>${UI.esc(a.firstName + " " + a.lastName)}</strong><small class="mono">${UI.esc(a.id)}</small></div></div>` },
        { key: "programmeId", label: "Programme", render: (a) => `<span class="small">${UI.esc(Programmes.name(a.programmeId))}</span>` },
        { key: "fee", label: "Fee", cls: "num", render: (a) => UI.naira(a.fee) },
        { key: "discountAmount", label: "Discount", cls: "num", render: (a) => `<span style="color:var(--success);font-weight:700">−${UI.naira(a.discountAmount)}</span>` },
        { key: "amountPayable", label: "Payable", cls: "num", render: (a) => `<b>${UI.naira(a.amountPayable)}</b>` },
        { key: "paymentStatus", label: "Payment", render: (a) => UI.badge(a.paymentStatus) }
    ];
    let table = null, mode = null;
    function refresh() {
        tabs(); types();
        const q = UI.$("#schSearch").value.toLowerCase();
        const wantEB = tab === "Early Bird";
        if (mode !== wantEB) {
            mode = wantEB;
            table = UI.dataTable("#schTable", wantEB
                ? { columns: ebCols, pageSize: 10, onRowClick: (id) => Applications.openDetail(id, refresh) }
                : { columns: schCols, pageSize: 10, onRowClick: (id) => review(id), empty: { icon: "fa-award", title: "No scholarship requests here", text: "Requests submitted by applicants will appear in this list." } });
        }
        if (wantEB) table.update(Applications.all().filter((a) => a.discountType === "earlybird" && (a.firstName + a.lastName + a.id).toLowerCase().includes(q)));
        else table.update(DB.all("scholarships").filter((s) => (tab === "History" || s.status === tab) && (s.name + s.applicationId + s.evidence).toLowerCase().includes(q)).sort((a, b) => new Date(b.reviewedAt || b.createdAt) - new Date(a.reviewedAt || a.createdAt)));
    }

    function review(id) {
        const s = DB.get("scholarships", id);
        const a = Applications.get(s.applicationId);
        const prog = Programmes.get(s.programmeId);
        const isExc = s.type === "excellence";
        const eligible = a ? Discounts.excellenceEligible(a) : false;
        const pending = s.status === "Pending";
        const m = UI.modal({
            title: `${Applications.discountName(s.type)} review`, subtitle: `${UI.esc(s.name)} · ${UI.esc(prog.name)}`, size: "lg",
            body: `<div class="grid grid-2" style="gap:22px">
                <div>
                    <div class="kv mb-3"><div><small>Applicant</small><strong>${UI.esc(s.name)}</strong></div><div><small>Application</small><strong class="mono">${UI.esc(s.applicationId)}</strong></div>
                    <div><small>Programme fee</small><strong>${UI.naira(prog.fee)}</strong></div><div><small>Payment</small><strong>${a ? UI.badge(a.paymentStatus) : "—"}</strong></div>
                    <div class="full"><small>Evidence</small><strong>${UI.esc(s.evidence)}</strong></div></div>
                    ${isExc ? `<div class="alert ${eligible ? "success" : "warning"}"><i class="fa-solid ${eligible ? "fa-circle-check" : "fa-triangle-exclamation"}"></i><p>${eligible ? `Declared WAEC ${a.waecYear} with ${a.numAs} A's meets the criteria (2020-date, 5+ A's). Verify the uploaded result before approving.` : "Declared result does not meet the Excellence Award criteria."}</p></div>
                        <label class="check mt-2"><input type="checkbox" id="rvVerified" ${!pending ? "checked disabled" : ""}> I have verified the WAEC result${a?.resultFile ? ` (<i class="fa-regular fa-file-pdf"></i> ${UI.esc(a.resultFile)})` : " with the WAEC portal"}</label>` :
                        `<div class="field"><label for="rvScore">Intake exam / interview score (%)</label><input id="rvScore" type="number" min="0" max="100" class="input" value="${s.interviewScore || ""}" ${pending ? "" : "disabled"} placeholder="e.g. 86"></div>`}
                </div>
                <div>
                    <div class="field"><label for="rvPct">Award percentage: <b id="rvPctLbl">${s.awardedPct || s.requestedPct}%</b></label><input id="rvPct" type="range" min="${isExc ? 50 : 5}" max="${isExc ? 50 : 40}" step="5" value="${s.awardedPct || s.requestedPct}" ${pending && !isExc ? "" : "disabled"} style="accent-color:var(--primary)"></div>
                    <div class="fee-box mt-2" id="rvCalc"></div>
                    ${pending ? `<div class="field mt-2"><label for="rvNote">Reviewer note (optional)</label><textarea id="rvNote" class="textarea" style="min-height:70px" placeholder="Visible in history"></textarea></div>` : `<div class="alert mt-2"><i class="fa-solid fa-clock-rotate-left"></i><p>${s.status} by <b>${UI.esc(s.reviewedBy || "Admissions")}</b> on ${UI.dateTime(s.reviewedAt)}${s.note ? ` — “${UI.esc(s.note)}”` : ""}</p></div>`}
                </div></div>`,
            footer: pending ? `<button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-soft-danger" id="rvReject"><i class="fa-solid fa-xmark"></i> Reject</button><button class="btn btn-success" id="rvApprove"><i class="fa-solid fa-check"></i> Approve award</button>` : `<button class="btn btn-primary" data-close>Close</button>`
        });
        const pctI = UI.$("#rvPct", m.el);
        function calc() {
            const pct = +pctI.value, disc = Math.round(prog.fee * pct / 100), payable = prog.fee - disc;
            UI.$("#rvPctLbl", m.el).textContent = pct + "%";
            const paid = a?.paymentStatus === "Paid" ? a.amountPayable : 0;
            const refund = Math.max(0, paid - payable);
            UI.$("#rvCalc", m.el).innerHTML = `<div class="fee-row"><span>Programme fee</span><span>${UI.naira(prog.fee)}</span></div><div class="fee-row"><span>${Applications.discountName(s.type)} (${pct}%)</span><span class="neg">−${UI.naira(disc)}</span></div><div class="fee-row total"><span>New payable</span><span>${UI.naira(payable)}</span></div>${paid ? `<div class="fee-row"><span>Already paid</span><span>${UI.naira(paid)}</span></div><div class="fee-row"><span><b>Refund due</b></span><span class="neg">${UI.naira(refund)}</span></div>` : ""}`;
            return { pct, disc, payable, refund };
        }
        pctI.addEventListener("input", calc); calc();
        UI.$("#rvScore", m.el)?.addEventListener("input", (e) => { const sc = +e.target.value; if (sc) { pctI.value = sc >= 90 ? 40 : sc >= 80 ? 30 : sc >= 70 ? 20 : sc >= 60 ? 10 : 5; calc(); } });
        const note = () => UI.$("#rvNote", m.el)?.value.trim();
        UI.$("#rvApprove", m.el)?.addEventListener("click", () => {
            if (isExc && !UI.$("#rvVerified", m.el).checked) { UI.toast("Verification required", "Confirm you have verified the WAEC result.", "warning"); return; }
            if (!isExc && !UI.$("#rvScore", m.el).value) { UI.toast("Score required", "Enter the intake exam/interview score.", "warning"); UI.$("#rvScore", m.el).focus(); return; }
            const c = calc();
            const now = new Date().toISOString();
            const reviewer = Auth.current()?.name || "Admissions Office";
            DB.update("scholarships", id, { status: "Approved", awardedPct: c.pct, interviewScore: isExc ? null : +UI.$("#rvScore", m.el).value, reviewedAt: now, reviewedBy: reviewer, note: note() });
            if (a && c.pct > (a.discountPct || 0)) {
                const hist = [...a.history, { at: now, text: `${Applications.discountName(s.type)} approved (${c.pct}%) — replaces ${a.discountType ? Applications.discountName(a.discountType) : "no discount"}`, ok: true }];
                const patch = { discountType: s.type, discountPct: c.pct, discountAmount: c.disc, history: hist };
                if (a.paymentStatus === "Paid" && c.refund > 0) {
                    const ref = ZainpaySimulator.generateTransactionReference() + "-RF";
                    DB.insert("payments", { id: ref, ref, applicationId: a.id, studentId: a.studentId, name: s.name, email: a.email, programmeId: a.programmeId, amount: c.refund, fee: prog.fee, discount: 0, gateway: "Zainpay", channel: "transfer", status: "REFUNDED", partial: true, description: `${Applications.discountName(s.type)} adjustment refund`, createdAt: now, verifiedAt: now, refundedAt: now });
                    hist.push({ at: now, text: `Refund of ${UI.naira(c.refund)} issued via Zainpay (${ref})`, ok: true });
                } else if (a.paymentStatus !== "Paid") patch.amountPayable = c.payable;
                DB.update("applications", a.id, patch);
            }
            Notifications.push(a?.email, "Scholarship approved", `Your scholarship application has been approved (${Applications.discountName(s.type)} — ${c.pct}%).${c.refund && a?.paymentStatus === "Paid" ? ` A refund of ${UI.naira(c.refund)} has been issued.` : ""}`, "scholarship");
            m.close(); UI.toast("Award approved", `${s.name} — ${c.pct}% ${Applications.discountName(s.type)}`, "success"); refresh();
        });
        UI.$("#rvReject", m.el)?.addEventListener("click", async () => {
            if (!(await UI.confirm({ title: "Reject this request?", message: `${UI.esc(s.name)} keeps any automatic discount already applied.`, confirmText: "Reject", tone: "danger", icon: "fa-award" }))) return;
            DB.update("scholarships", id, { status: "Rejected", reviewedAt: new Date().toISOString(), reviewedBy: Auth.current()?.name || "Admissions Office", note: note() || (isExc ? "Result did not meet criteria" : "Score below threshold") });
            Notifications.push(a?.email, "Scholarship update", `Your ${Applications.discountName(s.type)} request was not approved this time.`, "scholarship");
            m.close(); UI.toast("Request rejected", s.name, "warning"); refresh();
        });
    }
    UI.$("#schSearch").addEventListener("input", UI.debounce(refresh, 150));
    UI.$("#schExport").onclick = () => UI.downloadCSV("tsce-scholarships.csv", DB.all("scholarships").map((s) => ({ ID: s.id, Applicant: s.name, Application: s.applicationId, Programme: Programmes.name(s.programmeId), Type: Applications.discountName(s.type), Requested: s.requestedPct + "%", Awarded: s.awardedPct ? s.awardedPct + "%" : "", Status: s.status, Evidence: s.evidence, ReviewedBy: s.reviewedBy || "", ReviewedAt: s.reviewedAt ? UI.date(s.reviewedAt) : "" })));
    refresh();
};
