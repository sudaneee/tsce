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
    const cfg = () => Site.settings?.discounts || { earlybird: 15, excellence: 50, excellenceMinYear: 2020, excellenceMinAs: 5, earlyBirdOpen: false };
    const deadline = () => Site.day(Site.settings?.admissions?.earlyBirdDeadline);
    const lastDay = () => { const d = deadline(); if (!d) return null; d.setDate(d.getDate() - 1); return d; };
    function rules() {
        const c = cfg();
        return {
            earlybird: { id: "earlybird", name: "Early Bird Discount", pct: c.earlybird, icon: "fa-bolt", condition: deadline() ? `Payment before ${UI.dateLong(deadline())}` : "Payment before the early-bird deadline", mode: "automatic" },
            excellence: { id: "excellence", name: "Excellence Award", pct: c.excellence, icon: "fa-award", condition: `WAEC/NECO results from ${c.excellenceMinYear} to date with ${c.excellenceMinAs} A's or more, verified in person at TSCE`, mode: "verification" }
        };
    }
    const earlyBirdOpen = () => !!cfg().earlyBirdOpen;
    const excellenceEligible = (d) => d.waecStatus === "Available" && +d.waecYear >= cfg().excellenceMinYear && +d.numAs >= cfg().excellenceMinAs;

    function evaluate(d) {
        const R = rules(), c = cfg(), eb = earlyBirdOpen(), ex = excellenceEligible(d);
        return [
            { ...R.earlybird, eligible: eb, reason: eb ? `Applies if you pay the programme fee before ${UI.dateLong(deadline())}.` : lastDay() ? `The early-bird window closed on ${UI.dateLong(lastDay())}.` : "The early-bird offer has closed." },
            { ...R.excellence, eligible: ex, reason: ex ? `WAEC ${d.waecYear} with ${d.numAs} A's — eligible. If you request it, bring the original result to TSCE; admission is confirmed after verification.` : `Requires WAEC/NECO (${c.excellenceMinYear} or later) with at least ${c.excellenceMinAs} A's.` }
        ];
    }
    /** Programme fee if paid today: only the automatic early bird (the server re-checks at payment). */
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
    if (!user) {
        UI.$("#wizardRoot").innerHTML = `<div class="card">${UI.empty({ icon: "fa-user-plus", title: "Create an account to apply", text: "Applications are made from your TSCE account, so you can pay, follow your admission and come back any time. Parents can apply for several children from one account.", action: `<a class="btn btn-primary" href="register.html">Create an account</a> <a class="btn btn-ghost" href="login.html?role=student">Sign in</a>` })}</div>`;
        return;
    }
    if (["staff", "admin"].includes(user.role)) {
        UI.$("#wizardRoot").innerHTML = `<div class="card">${UI.empty({ icon: "fa-id-badge", title: "You're signed in with a staff account", text: "Staff accounts can't apply. Sign out to apply with a personal email.", action: `<button class="btn btn-primary" onclick="Auth.logout()">Sign out</button>` })}</div>`;
        return;
    }

    // Drafts live in sessionStorage: they survive a reload but not closing the tab,
    // so personal details aren't left behind on shared (e.g. cybercafé) computers.
    const drafts = {
        key: `tsce_appDraft_${user.id}`,
        get() { try { return JSON.parse(sessionStorage.getItem(this.key)); } catch (e) { return null; } },
        set(v) { try { sessionStorage.setItem(this.key, JSON.stringify(v)); } catch (e) { /* ignore */ } },
        clear() { try { sessionStorage.removeItem(this.key); } catch (e) { /* ignore */ } }
    };

    // Populate selects
    UI.$("#a_state").innerHTML = `<option value="">Select state</option>` + STATES.map((s) => `<option>${s}</option>`).join("");
    UI.$("#a_state").addEventListener("change", () => { UI.$("#lgaList").innerHTML = (LGAS[UI.$("#a_state").value] || []).map((l) => `<option value="${l}">`).join(""); });
    UI.$("#a_intake").innerHTML = `<option value="${UI.esc(adm.intake)}">${UI.esc(adm.intake)} — starts ${UI.date(Site.day(adm.cohortDate))}</option>`;

    // A parent fills in the child's details; a self-applicant applies as themselves.
    const parent = user.role === "parent";
    const emailI = UI.$("#a_email"), emailField = emailI.closest(".field");
    if (parent) {
        panels[0].dataset.title = "Applicant's details";
        panels[0].dataset.sub = "Details of the child or ward you're applying for. Fields marked * are required.";
        emailI.required = false;
        emailField.querySelector("label").innerHTML = `Child's email <span class="muted small">(optional)</span>`;
        emailField.querySelector(".hint").textContent = `Only if your child has their own email. Updates and receipts go to ${user.email}.`;
        UI.$("#a_phone").closest(".field").querySelector("label").innerHTML = `Phone (child or parent) <span class="req">*</span>`;
        if (!UI.$("#a_phone").value) UI.$("#a_phone").value = user.phone || "";
    } else {
        emailI.value = user.email;
        emailI.readOnly = true;
        emailField.querySelector(".hint").textContent = `Signed in as ${user.email}.`;
        const [first, ...rest] = (user.name || "").split(" ");
        if (!UI.$("#a_first").value) UI.$("#a_first").value = first || "";
        if (!UI.$("#a_last").value) UI.$("#a_last").value = rest.pop() || "";
        if (!UI.$("#a_phone").value) UI.$("#a_phone").value = user.phone || "";
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

    // Draft autosave (never the password or the file)
    function data() { return { ...UI.formData(form), programmeId }; }
    function saveDraft() { const d = data(); drafts.set({ ...d, step }); UI.$("#draftNote").textContent = "Draft saved " + new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" }); }
    function loadDraft() {
        const d = drafts.get();
        if (!d) return;
        Object.entries(d).forEach(([k, v]) => { const el = form.elements[k]; if (!el || k === "step" || (k === "email" && !parent)) return; if (el instanceof RadioNodeList) { UI.$$(`input[name="${k}"]`, form).forEach((r) => r.checked = r.value === v); } else if (el.type !== "file") el.value = v; });
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
            const ctrl = isEB ? "" : `<label class="check mt-1" style="font-size:.84rem"><input type="radio" name="awardRequest" value="${r.id}" ${selected === r.id ? "checked" : ""} ${r.eligible ? "" : "disabled"}> Request the Excellence Award (admission after in-person verification)</label>`;
            return `<div class="discount-card ${cls}"><div class="pct-pill">${r.upTo ? "≤" : ""}${r.pct}%</div><div style="flex:1"><div class="flex between" style="align-items:flex-start"><h4>${r.name}</h4>${isEB || r.id === "excellence" ? status : ""}</div><p>${r.condition}</p><p class="mt-1" style="color:var(--text-2)">${r.reason}</p>${ctrl}</div></div>`;
        }).join("") + `<label class="check" style="font-size:.84rem;padding:4px 4px 0"><input type="radio" name="awardRequest" value="none" ${selected === "none" ? "checked" : ""}> No award — admit me straight away</label>`;

        const appFee = adm.applicationFee || 0, charge = Site.settings?.payments?.payerCharge || 0;
        UI.$("#feeCalc").innerHTML = `<div class="fee-box"><div class="fee-head"><strong style="font-family:var(--font-head)">After admission: one payment</strong><span class="badge badge-primary no-dot">${UI.esc(d.intake)}</span></div>
            <div class="fee-row"><span>${UI.esc(p.name)}</span><span>${UI.naira(fees.fee)}</span></div>
            ${fees.discount ? `<div class="fee-row"><span>Early Bird Discount (${fees.pct}%)</span><span class="neg">−${UI.naira(fees.discount)}</span></div>` : ""}
            ${appFee ? `<div class="fee-row"><span>Application fee</span><span>${UI.naira(appFee)}</span></div>` : ""}
            ${charge ? `<div class="fee-row"><span>Zainpay transaction charge</span><span>${UI.naira(charge)}</span></div>` : ""}
            <div class="fee-row total"><span>Total${fees.discount ? " if paid now" : ""}</span><span>${UI.naira(fees.payable + appFee + charge)}</span></div></div>
            <p class="hint mt-1"><i class="fa-solid fa-circle-info"></i> Nothing to pay to apply. Without an award request you're admitted as soon as you submit, then pay the programme fee (it includes the ${UI.naira(appFee)} application fee) to secure the seat. Discounts apply to the programme fee only and don't stack: an approved Excellence Award (${Discounts.RULES.excellence.pct}%) replaces the early bird.</p>`;

        const r = (k, v) => `<div><small>${k}</small><strong>${UI.esc(v || "—")}</strong></div>`;
        UI.$("#reviewGrid").innerHTML = r("Full name", [d.firstName, d.middleName, d.lastName].filter(Boolean).join(" ")) + r("Email", d.email) + r("Phone", d.phone) + r("Gender · DOB", `${d.gender} · ${UI.date(d.dob)}`) + r("State · LGA", `${d.state} · ${d.lga}`) + r("Qualification", `${d.qualification} — ${d.institution}`) + r("WAEC/NECO", d.waecStatus === "Available" ? `${d.waecYear} · ${d.numAs} A's${waecFile ? " · result attached" : ""}` : d.waecStatus) + r("Programme", p.name) + r("Schedule", d.schedule) + r("Intake", d.intake);
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
        fd.append("declare", UI.$("#a_declare").checked ? "true" : "false");
        if (waecFile && d.waecStatus === "Available") fd.append("resultFile", waecFile);
        try {
            const res = await API.post("applications", fd);
            drafts.clear();
            if (res.status === "Admitted") {
                UI.toast("Admitted!", `${res.id} — pay the programme fee to secure the seat`, "success");
                setTimeout(() => location.href = `payment.html?app=${encodeURIComponent(res.id)}`, 500);
            } else {
                UI.toast("Application submitted", `${res.id} — bring the original WAEC/NECO result to TSCE`, "success");
                setTimeout(() => location.href = `my-applications.html#${encodeURIComponent(res.id)}`, 500);
            }
            return;
        } catch (err) {
            if (err.code === "duplicate_application") {
                const no = err.data?.extra?.applicationId;
                UI.modal({
                    title: "Already applied", size: "sm", body: `<p>${UI.esc(err.message)}</p><p class="muted small">You can follow it, and pay any outstanding fee, from My applications.</p>`,
                    footer: `<button class="btn btn-ghost" data-close>Close</button><a class="btn btn-primary" href="my-applications.html#${encodeURIComponent(no || "")}">My applications</a>`
                });
            } else if (Object.keys(err.fields || {}).length) {
                showServerErrors(err);
                UI.toast("Please check your application", err.message, "warning");
            } else {
                UI.toast("Couldn't submit application", err.message, "error");
            }
        }
        btn.disabled = false; btn.innerHTML = `<i class="fa-solid fa-paper-plane"></i> Submit application`;
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

/* Staff applications and Excellence Awards: see js/staff.js (API-backed, Phase 5). */

/* ---------------- Applicant / parent home: My applications ---------------- */
Pages["my-applications"] = async function () {
    const root = UI.$("#maRoot");
    const user = Auth.current();
    if (!user) { location.replace(UI.url("pages/login.html?role=student")); return; }
    if (["staff", "admin"].includes(user.role)) { location.replace(Auth.homeFor(user.role, user)); return; }
    const parent = user.role === "parent";
    UI.$("#maSub").textContent = parent
        ? `Signed in as ${user.name} (parent / guardian). Apply and pay for each of your children here.`
        : `Signed in as ${user.name}.`;
    UI.$("#maNew").innerHTML = `<i class="fa-solid fa-plus"></i> ${parent ? "Apply for a child" : "New application"}`;
    UI.$("#maLogout").onclick = () => Auth.logout();
    if (!Site.settings?.admissions?.open) UI.$("#maNew").classList.add("hidden");

    root.innerHTML = `<div class="card">${UI.skeleton(5)}</div>`;
    let apps;
    try { apps = await API.get("applications"); }
    catch (e) { root.innerHTML = `<div class="card">${UI.empty({ icon: "fa-plug-circle-xmark", title: "Couldn't load your applications", text: UI.esc(e.message) })}</div>`; return; }
    if (!apps.length) {
        root.innerHTML = `<div class="card">${UI.empty({ icon: "fa-file-signature", title: "No applications yet", text: parent ? "Apply for your child (or several children) — each gets their own application." : "Choose a programme and apply in about 5 minutes.", action: `<a class="btn btn-primary" href="application.html">${parent ? "Apply for a child" : "Start application"}</a>` })}</div>`;
        return;
    }

    const charge = Site.settings?.payments?.payerCharge || 0;
    const address = Site.settings?.institution?.address || "TSCE";
    const pay = (a) => `<a class="btn btn-grad" href="payment.html?app=${encodeURIComponent(a.id)}&purpose=programme_fee"><i class="fa-solid fa-lock"></i> Pay programme fee · ${UI.naira(a.amountPayable + charge)}</a>`;
    const STEPS = ["Applied", "Admission", "Programme fee", "Enrolled"];
    const stage = { Pending: 1, "Awaiting Verification": 1, Admitted: 2, Enrolled: 4, Rejected: 1 };

    function tracker(a) {
        const idx = stage[a.status] ?? 1, rejected = a.status === "Rejected";
        return `<div class="lifecycle">${STEPS.map((s, i) => {
            const bad = rejected && i === 1, done = i < idx && !bad, cur = !rejected && i === idx;
            return `<div class="lc-step ${done ? "done" : cur ? "current" : ""} ${bad ? "bad" : ""}"><div class="c">${done ? '<i class="fa-solid fa-check"></i>' : bad ? '<i class="fa-solid fa-xmark"></i>' : i + 1}</div>${bad ? "Not admitted" : s}</div>`;
        }).join("")}</div>`;
    }
    function next(a) {
        const award = a.awardRequest;
        switch (a.status) {
            case "Pending":
                return `<div class="alert mb-2"><i class="fa-solid fa-circle-info"></i><p>This application is being processed.</p></div>`;
            case "Awaiting Verification":
                return `<div class="alert warning"><i class="fa-solid fa-id-card"></i><p><b>Next step: visit TSCE with the original WAEC/NECO result</b> (${UI.esc(address)}). Admissions will verify it and approve the Excellence Award. You'll then be able to pay the programme fee here.</p></div>`;
            case "Admitted":
                return `<div class="alert success mb-2"><i class="fa-solid fa-circle-check"></i><p><b>Admitted!</b> ${award?.status === "Approved" ? `Excellence Award approved — ${award.awardedPct}% off. ` : award?.status === "Rejected" ? "The Excellence Award was not approved, so the normal fee applies. " : ""}Pay the programme fee to secure ${parent ? "the" : "your"} seat (seats are limited).</p></div>
                    <div class="flex flex-wrap" style="align-items:center">${pay(a)}<span class="small muted">${UI.naira(a.fee)}${a.discountAmount ? ` − ${Applications.discountName(a.discountType)} ${UI.naira(a.discountAmount)}` : ""}${a.applicationFeeDue ? ` + application fee ${UI.naira(a.applicationFeeDue)}` : " · application fee already paid"}</span></div>`;
            case "Enrolled":
                return `<div class="alert success mb-2"><i class="fa-solid fa-user-graduate"></i><p><b>Enrolled.</b> Student number <b class="mono">${UI.esc(a.studentId || "")}</b>. Classes begin ${UI.dateLong(Site.day(a.cohortStart))}.</p></div>
                    <div class="flex flex-wrap">${a.txRef ? `<a class="btn btn-outline" href="success.html?ref=${encodeURIComponent(a.txRef)}&fresh=0"><i class="fa-solid fa-receipt"></i> Confirmation &amp; receipt</a>` : ""}${!parent ? `<a class="btn btn-primary" href="student/dashboard.html"><i class="fa-solid fa-user-graduate"></i> Student portal</a>` : ""}</div>`;
            case "Rejected":
                return `<div class="alert danger"><i class="fa-solid fa-circle-xmark"></i><p>This application was not successful. Contact the admissions office if you have questions.</p></div>`;
            default:
                return "";
        }
    }
    root.innerHTML = `<div class="stack">${apps.map((a) => `<article class="card card-pad" id="${UI.esc(a.id)}">
        <div class="flex between flex-wrap mb-2" style="align-items:flex-start">
            <div class="flex" style="align-items:flex-start">${UI.avatar(a.name)}<div><h3 class="mb-0" style="font-size:1.1rem">${UI.esc(a.name)}</h3>
                <div class="small muted">${UI.esc(a.programmeName)} · ${UI.esc(a.intake)}</div><div class="small muted mono">${UI.esc(a.id)}</div></div></div>
            ${UI.badge(a.status)}</div>
        ${tracker(a)}${next(a)}</article>`).join("")}</div>`;
    if (location.hash) document.getElementById(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView({ behavior: "smooth" });
};
