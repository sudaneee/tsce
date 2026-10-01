/* ==========================================================================
   TSCE — Reports (staff): six management reports with CSV export & print
   ========================================================================== */

const Reports = (() => {
    const inRange = (d, from, to) => (!from || d.slice(0, 10) >= from) && (!to || d.slice(0, 10) <= to);

    /** Each report returns { summary:[[label,value]], rows:[{}], chart:{} } for the current filters. */
    const DEFS = {
        applications: {
            title: "Application Report", icon: "fa-file-signature", tone: "", desc: "All applications with status, payment and discount.",
            build: ({ prog, from, to }) => {
                const A = Applications.all().filter((a) => (!prog || a.programmeId === prog) && inRange(a.createdAt, from, to));
                const by = Applications.STATUSES.map((s) => A.filter((a) => a.status === s).length);
                return {
                    summary: [["Applications", A.length], ["Paid", A.filter((a) => a.paymentStatus === "Paid").length], ["Enrolled", A.filter((a) => a.status === "Enrolled").length], ["Conversion", A.length ? Math.round(A.filter((a) => a.paymentStatus === "Paid").length / A.length * 100) + "%" : "—"]],
                    rows: A.map((a) => ({ "Application ID": a.id, Applicant: Applications.fullName(a), Programme: Programmes.name(a.programmeId), Intake: a.intake, Date: UI.date(a.createdAt), "Fee (₦)": a.fee, "Discount (₦)": a.discountAmount || 0, "Payable (₦)": a.amountPayable, Payment: a.paymentStatus, Status: a.status })),
                    chart: { type: "bar", data: { labels: Applications.STATUSES, datasets: [{ data: by, backgroundColor: ["#F5B400", "#0EA5E9", "#1846D6", "#12A150", "#0B1D55", "#DC2F45"], borderRadius: 8, maxBarThickness: 40 }] }, options: { plugins: { legend: { display: false } } } }
                };
            }
        },
        enrollment: {
            title: "Student Enrollment Report", icon: "fa-user-graduate", tone: "cyan", desc: "Enrolled students by programme, cohort and status.",
            build: ({ prog }) => {
                const S = Students.all().filter((s) => !prog || s.programmeId === prog);
                const progs = Programmes.all().filter((p) => !prog || p.id === prog);
                return {
                    summary: [["Students", S.length], ["Active", S.filter((s) => s.status === "Active").length], ["Graduated", S.filter((s) => s.status === "Completed").length], ["Female / Male", `${S.filter((s) => s.gender === "Female").length} / ${S.filter((s) => s.gender === "Male").length}`]],
                    rows: S.map((s) => ({ "Student ID": s.id, Name: Students.fullName(s), Gender: s.gender, State: s.state, Programme: Programmes.name(s.programmeId), Cohort: s.cohort, "Progress %": s.progress, Status: s.status })),
                    chart: { type: "bar", data: { labels: progs.map((p) => p.code.replace("TSCE-", "")), datasets: [{ label: "Active", data: progs.map((p) => S.filter((s) => s.programmeId === p.id && s.status === "Active").length), backgroundColor: "#1846D6", borderRadius: 6 }, { label: "Graduated", data: progs.map((p) => S.filter((s) => s.programmeId === p.id && s.status === "Completed").length), backgroundColor: "#06C8E0", borderRadius: 6 }] }, options: { scales: { x: { stacked: true }, y: { stacked: true } } } }
                };
            }
        },
        revenue: {
            title: "Revenue Report", icon: "fa-naira-sign", tone: "green", desc: "Verified Zainpay collections, refunds and outstanding.",
            build: ({ prog, from, to }) => {
                const P = Payments.all().filter((p) => (!prog || p.programmeId === prog) && inRange(p.createdAt, from, to));
                const sum = (st) => P.filter((p) => p.status === st).reduce((t, p) => t + p.amount, 0);
                const progs = Programmes.all().filter((p) => !prog || p.id === prog);
                return {
                    summary: [["Collected", UI.naira(sum("SUCCESS"))], ["Pending", UI.naira(sum("PENDING"))], ["Refunded", UI.naira(sum("REFUNDED"))], ["Transactions", P.length]],
                    rows: P.map((p) => ({ Reference: p.ref, Payer: p.name, Programme: Programmes.name(p.programmeId), "Amount (₦)": p.amount, Channel: Payments.CHANNEL[p.channel], Gateway: "Zainpay", Status: p.status, Date: UI.dateTime(p.createdAt) })),
                    chart: { type: "doughnut", data: { labels: progs.map((p) => p.name), datasets: [{ data: progs.map((pr) => P.filter((p) => p.programmeId === pr.id && p.status === "SUCCESS").reduce((t, p) => t + p.amount, 0)), backgroundColor: progs.map((p) => p.color), borderWidth: 0 }] }, options: { cutout: "62%", plugins: { legend: { position: "right", labels: { font: { size: 11 } } }, tooltip: { callbacks: { label: (c) => `${c.label}: ${UI.naira(c.raw)}` } } } } }
                };
            }
        },
        attendance: {
            title: "Attendance Report", icon: "fa-calendar-check", tone: "gold", desc: "Attendance rates per student with at-risk flags.",
            build: ({ prog, from, to }) => {
                const S = Students.all().filter((s) => !prog || s.programmeId === prog);
                const rows = S.map((s) => { const r = DB.where("attendance", (a) => a.studentId === s.id && inRange(a.date, from, to)); const ok = r.filter((a) => a.status !== "Absent").length; return { s, total: r.length, present: r.filter((a) => a.status === "Present").length, late: r.filter((a) => a.status === "Late").length, absent: r.filter((a) => a.status === "Absent").length, rate: r.length ? Math.round(ok / r.length * 100) : 0 }; }).filter((x) => x.total);
                const avg = rows.length ? Math.round(rows.reduce((t, x) => t + x.rate, 0) / rows.length) : 0;
                const bands = [["95–100%", (r) => r >= 95], ["85–94%", (r) => r >= 85 && r < 95], ["75–84%", (r) => r >= 75 && r < 85], ["Below 75%", (r) => r < 75]];
                return {
                    summary: [["Average rate", avg + "%"], ["Students tracked", rows.length], ["Sessions logged", rows.reduce((t, x) => t + x.total, 0)], ["At risk (<75%)", rows.filter((x) => x.rate < 75).length]],
                    rows: rows.map((x) => ({ "Student ID": x.s.id, Name: Students.fullName(x.s), Programme: Programmes.name(x.s.programmeId), Sessions: x.total, Present: x.present, Late: x.late, Absent: x.absent, "Rate %": x.rate, Flag: x.rate < 75 ? "AT RISK" : "OK" })),
                    chart: { type: "bar", data: { labels: bands.map((b) => b[0]), datasets: [{ data: bands.map((b) => rows.filter((x) => b[1](x.rate)).length), backgroundColor: ["#12A150", "#1846D6", "#F5B400", "#DC2F45"], borderRadius: 8, maxBarThickness: 48 }] }, options: { plugins: { legend: { display: false } } } }
                };
            }
        },
        scholarships: {
            title: "Scholarship Report", icon: "fa-award", tone: "gold", desc: "Excellence awards, scholarships and early-bird discounts.",
            build: ({ prog }) => {
                const S = DB.all("scholarships").filter((s) => !prog || s.programmeId === prog);
                const A = Applications.all().filter((a) => (!prog || a.programmeId === prog) && a.discountAmount && a.paymentStatus === "Paid");
                const types = ["earlybird", "excellence", "scholarship"];
                return {
                    summary: [["Award requests", S.length], ["Approved", S.filter((s) => s.status === "Approved").length], ["Pending", S.filter((s) => s.status === "Pending").length], ["Discount value", UI.naira(A.reduce((t, a) => t + a.discountAmount, 0))]],
                    rows: S.map((s) => ({ ID: s.id, Applicant: s.name, Application: s.applicationId, Programme: Programmes.name(s.programmeId), Type: Applications.discountName(s.type), "Requested %": s.requestedPct, "Awarded %": s.awardedPct || "", Status: s.status, Evidence: s.evidence, "Reviewed by": s.reviewedBy || "" })),
                    chart: { type: "doughnut", data: { labels: types.map(Applications.discountName), datasets: [{ data: types.map((t) => A.filter((a) => a.discountType === t).reduce((x, a) => x + a.discountAmount, 0)), backgroundColor: ["#12A150", "#F5B400", "#1846D6"], borderWidth: 0 }] }, options: { cutout: "62%", plugins: { legend: { position: "bottom" }, tooltip: { callbacks: { label: (c) => `${c.label}: ${UI.naira(c.raw)}` } } } } }
                };
            }
        },
        performance: {
            title: "Programme Performance Report", icon: "fa-ranking-star", tone: "", desc: "Enrolment, scores, attendance and completion by programme.",
            build: ({ prog }) => {
                const progs = Programmes.all().filter((p) => !prog || p.id === prog);
                const rows = progs.map((p) => {
                    const S = Students.all().filter((s) => s.programmeId === p.id);
                    const R = DB.where("results", (r) => r.programmeId === p.id && r.status === "Published");
                    const AT = DB.where("attendance", (a) => a.programmeId === p.id);
                    const rev = Payments.all().filter((x) => x.programmeId === p.id && x.status === "SUCCESS").reduce((t, x) => t + x.amount, 0);
                    const seat = Programmes.seats(p);
                    return { p, students: S.length, avg: R.length ? Math.round(R.reduce((t, r) => t + r.score, 0) / R.length) : 0, att: AT.length ? Math.round(AT.filter((a) => a.status !== "Absent").length / AT.length * 100) : 0, completion: S.length ? Math.round(S.filter((s) => s.status === "Completed").length / S.length * 100) : 0, rev, fill: seat.pct };
                });
                const best = [...rows].sort((a, b) => b.avg - a.avg)[0];
                return {
                    summary: [["Programmes", rows.length], ["Top performing", best ? best.p.code.replace("TSCE-", "") + ` (${best.avg}%)` : "—"], ["Avg. seat fill", rows.length ? Math.round(rows.reduce((t, r) => t + r.fill, 0) / rows.length) + "%" : "—"], ["Revenue", UI.naira(rows.reduce((t, r) => t + r.rev, 0), { compact: true })]],
                    rows: rows.map((r) => ({ Programme: r.p.name, "Fee (₦)": r.p.fee, Weeks: r.p.weeks, "Seat fill %": r.fill, Students: r.students, "Avg score %": r.avg, "Attendance %": r.att, "Completion %": r.completion, "Revenue (₦)": r.rev })),
                    chart: { type: "bar", data: { labels: rows.map((r) => r.p.code.replace("TSCE-", "")), datasets: [{ label: "Avg score %", data: rows.map((r) => r.avg), backgroundColor: "#1846D6", borderRadius: 6 }, { label: "Attendance %", data: rows.map((r) => r.att), backgroundColor: "#06C8E0", borderRadius: 6 }] }, options: { scales: { y: { min: 0, max: 100 } } } }
                };
            }
        }
    };
    return { DEFS };
})();

Pages["staff-reports"] = function (view) {
    let current = UI.param("r") || "applications";
    view.innerHTML = `
        <div class="view-head"><div><h2>Reports</h2><p>Management reports generated live from platform data. Export to CSV or print.</p></div></div>
        <div class="grid grid-3 mb-3" id="repCards"></div>
        <div class="panel" id="repPanel">
            <div class="panel-head"><div><h3 id="repTitle"></h3><p id="repDesc"></p></div>
                <div class="flex flex-wrap"><button class="btn btn-sm btn-outline" id="repCsv"><i class="fa-solid fa-file-csv"></i> Export CSV</button><button class="btn btn-sm btn-primary" id="repPrint"><i class="fa-solid fa-print"></i> Print Report</button></div></div>
            <div class="table-tools"><select class="select" id="rProg" aria-label="Programme"><option value="">All programmes</option>${Programmes.all().map((p) => `<option value="${p.id}">${UI.esc(p.name)}</option>`).join("")}</select>
                <label class="small muted" for="rFrom">From</label><input type="date" class="input" id="rFrom" style="width:auto"><label class="small muted" for="rTo">To</label><input type="date" class="input" id="rTo" style="width:auto"><span class="spacer"></span><span class="small muted" id="rGen"></span></div>
            <div id="repBody"></div>
        </div>`;
    UI.$("#repCards").innerHTML = Object.entries(Reports.DEFS).map(([k, d]) => `<button class="card card-pad card-hover" data-rep="${k}" style="text-align:left;cursor:pointer;display:flex;gap:14px;align-items:flex-start;font:inherit;color:inherit"><span class="icon-tile ${d.tone}"><i class="fa-solid ${d.icon}"></i></span><div><strong style="font-family:var(--font-head);display:block">${d.title}</strong><span class="small muted">${d.desc}</span></div></button>`).join("");
    let last = null;
    function render() {
        UI.$$("[data-rep]").forEach((c) => { const on = c.dataset.rep === current; c.style.borderColor = on ? "var(--primary)" : ""; c.style.boxShadow = on ? "0 0 0 3px rgba(24,70,214,.1)" : ""; c.setAttribute("aria-pressed", on); });
        const d = Reports.DEFS[current];
        UI.$("#repTitle").innerHTML = `<i class="fa-solid ${d.icon}"></i>${d.title}`;
        UI.$("#repDesc").textContent = d.desc;
        UI.$("#repBody").innerHTML = UI.skeleton(6);
        setTimeout(() => {
            last = d.build({ prog: UI.$("#rProg").value, from: UI.$("#rFrom").value, to: UI.$("#rTo").value });
            UI.$("#rGen").textContent = "Generated " + UI.dateTime(new Date());
            const cols = last.rows.length ? Object.keys(last.rows[0]) : [];
            UI.$("#repBody").innerHTML = `<div class="panel-body"><div class="kpis" style="margin-bottom:18px">${last.summary.map(([l, v]) => `<div class="kpi"><p class="label">${l}</p><div class="value" style="font-size:1.4rem">${v}</div></div>`).join("")}</div>
                <div class="chart-box"><canvas id="repChart"></canvas></div></div><div id="repTable"></div>`;
            Dashboard.chart("repChart", last.chart);
            UI.dataTable("#repTable", { rows: last.rows.map((r, i) => ({ ...r, id: i })), pageSize: 10, columns: cols.map((c) => ({ key: c, label: c, cls: /₦|%|Sessions|Present|Late|Absent|Students|Weeks/.test(c) ? "num" : "", render: (r) => typeof r[c] === "number" && /₦/.test(c) ? UI.naira(r[c]) : UI.esc(r[c]) })), empty: { icon: "fa-chart-pie", title: "No data for this report", text: "Try widening the date range or selecting all programmes." } });
        }, 250);
    }
    UI.$$("[data-rep]").forEach((c) => c.onclick = () => { current = c.dataset.rep; render(); UI.$("#repPanel").scrollIntoView({ behavior: "smooth", block: "start" }); });
    ["#rProg", "#rFrom", "#rTo"].forEach((s) => UI.$(s).onchange = render);
    UI.$("#repCsv").onclick = () => last && UI.downloadCSV(`tsce-${current}-report.csv`, last.rows);
    UI.$("#repPrint").onclick = () => {
        if (!last) return;
        const d = Reports.DEFS[current];
        const cols = last.rows.length ? Object.keys(last.rows[0]) : [];
        const img = UI.$("#repChart")?.toDataURL("image/png");
        UI.printHTML(d.title, `<div class="receipt"><div class="receipt-head"><div class="flex">${UI.logoFull("receipt-logo")}<div><h3>${TSCE_FLYER.name}</h3><p>${d.title} · ${UI.$("#rProg").value ? Programmes.name(UI.$("#rProg").value) : "All programmes"}</p></div></div><div style="text-align:right"><p>Generated ${UI.dateTime(new Date())}</p><p>Prepared by ${UI.esc(Auth.current()?.name || "")}</p></div></div>
            <div class="kpis">${last.summary.map(([l, v]) => `<div class="kpi"><p class="label">${l}</p><div class="value" style="font-size:1.2rem">${v}</div></div>`).join("")}</div>
            ${img ? `<img src="${img}" style="max-height:260px;margin:0 auto 18px" alt="">` : ""}
            <table class="table"><thead><tr>${cols.map((c) => `<th>${UI.esc(c)}</th>`).join("")}</tr></thead><tbody>${last.rows.map((r) => `<tr>${cols.map((c) => `<td>${UI.esc(typeof r[c] === "number" && /₦/.test(c) ? UI.naira(r[c]) : r[c])}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`);
    };
    render();
};
