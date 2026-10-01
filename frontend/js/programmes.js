/* ==========================================================================
   TSCE — Programmes: catalogue, cards, detail view, staff management
   ========================================================================== */

const Programmes = (() => {
    const all = () => Site.programmes;
    const active = () => all().filter((p) => p.status === "Active");
    const get = (id) => all().find((p) => p.id === id) || null;
    const name = (id) => get(id)?.name || "—";
    const tracks = () => [...new Set(all().map((p) => p.track))];

    /** Seats for the current intake, counted on the server (paid, not rejected). */
    function seats(p) {
        return p.seats || { enrolled: 0, capacity: p.capacity, available: p.capacity, pct: 0 };
    }

    function card(p) {
        const s = seats(p);
        return `<button class="prog-card reveal" data-prog="${p.id}" style="--pc:${p.color};--pc-bg:${p.colorBg}" aria-label="View ${UI.esc(p.name)} details">
            <div class="prog-top"><span class="icon-tile"><i class="fa-solid ${p.icon}"></i></span><span class="badge badge-neutral no-dot prog-track">${p.track}</span></div>
            <div class="prog-body">
                <h3>${UI.esc(p.name)}</h3>
                <p>${UI.esc(p.overview)}</p>
                <div class="prog-meta"><span><i class="fa-regular fa-clock"></i>${p.weeks} Weeks</span><span><i class="fa-solid fa-layer-group"></i>${p.modules.length} Modules</span>
                <span class="seats ${s.available > 8 ? "ok" : ""}"><i class="fa-solid fa-chair"></i>${s.available} seats left</span></div>
            </div>
            <div class="prog-foot"><div class="prog-fee">${UI.naira(p.fee)}<small>Programme fee</small></div><span class="prog-go"><i class="fa-solid fa-arrow-right"></i></span></div>
        </button>`;
    }

    function bindCards(rootEl) {
        UI.$$("[data-prog]", rootEl).forEach((b) => b.addEventListener("click", () => openDetail(b.dataset.prog)));
    }

    function openDetail(id) {
        const p = get(id);
        if (!p) return UI.toast("Programme not found", "", "error");
        const s = seats(p);
        const set = Site.settings?.admissions || {};
        const ebActive = Discounts.earlyBirdOpen();
        const eb = Discounts.compute(p.fee);
        const body = `
            <div class="pd-facts">
                <div><small>Duration</small><strong>${p.weeks} Weeks</strong></div>
                <div><small>Programme Fee</small><strong>${UI.naira(p.fee)}</strong></div>
                <div><small>Starts</small><strong>${UI.date(Site.day(set.cohortDate))}</strong></div>
                <div><small>Available Seats</small><strong>${s.available} / ${s.capacity}</strong></div>
            </div>
            <div style="padding:24px">
                ${ebActive ? `<div class="alert success mb-3"><i class="fa-solid fa-bolt"></i><p><b>Early-bird offer:</b> pay before ${UI.dateLong(Discounts.deadline())} and pay <b>${UI.naira(eb.payable)}</b> instead of ${UI.naira(p.fee)} (${eb.pct}% off).</p></div>` : ""}
                <div class="grid grid-2" style="gap:28px">
                    <div>
                        <div class="pd-section"><h4><i class="fa-solid fa-bullseye"></i>Overview</h4><p>${UI.esc(p.overview)}</p></div>
                        <div class="pd-section"><h4><i class="fa-solid fa-graduation-cap"></i>Learning outcomes</h4><ul class="checklist">${p.outcomes.map((o) => `<li>${UI.esc(o)}</li>`).join("")}</ul></div>
                        <div class="pd-section"><h4><i class="fa-solid fa-user-check"></i>Who should apply</h4><ul class="checklist">${p.audience.map((o) => `<li>${UI.esc(o)}</li>`).join("")}</ul></div>
                        <div class="pd-section"><h4><i class="fa-solid fa-clipboard-list"></i>Requirements</h4><ul class="checklist">${p.requirements.map((o) => `<li>${UI.esc(o)}</li>`).join("")}</ul></div>
                    </div>
                    <div>
                        <div class="pd-section"><h4><i class="fa-solid fa-book-open"></i>Curriculum</h4><ol class="curriculum">${p.modules.map((m, i) => `<li>${UI.esc(m)}<span>Wk ${Math.max(1, Math.round((i + 1) * p.weeks / p.modules.length))}</span></li>`).join("")}</ol></div>
                        <div class="pd-section"><h4><i class="fa-solid fa-briefcase"></i>Career opportunities</h4><div class="tag-list">${p.careers.map((c) => `<span class="chip">${UI.esc(c)}</span>`).join("")}</div></div>
                        <div class="pd-section"><h4><i class="fa-regular fa-calendar"></i>Training schedule & cohort</h4>
                            <ul class="checklist">${p.schedules.map((x) => `<li>${UI.esc(x)}</li>`).join("")}</ul>
                            <p class="small muted mt-2 mb-0">Intake: <b>${UI.esc(set.intake || "—")}</b> · Classes begin <b>${UI.dateLong(Site.day(set.cohortDate))}</b>${p.instructor ? ` · Lead instructor: <b>${UI.esc(p.instructor)}</b>` : ""}</p>
                        </div>
                        <div class="seat-meter"><div style="flex:1"><div class="flex between small mb-1"><b>${s.enrolled} enrolled</b><span class="muted">${s.available} seats left</span></div><div class="progress ${s.pct > 85 ? "gold" : ""}"><span data-value="${s.pct}"></span></div></div></div>
                    </div>
                </div>
            </div>`;
        const m = UI.modal({
            size: "xl", bare: true,
            body: `<div class="pd-hero"><div class="flex between" style="align-items:flex-start"><span class="badge badge-dark no-dot" style="background:rgba(255,255,255,.14)">${p.category} · ${p.track}</span><button class="modal-close" data-close aria-label="Close" style="background:rgba(255,255,255,.12);color:#fff"><i class="fa-solid fa-xmark"></i></button></div>
                <h2>${UI.esc(p.name)}</h2><p>${p.code} · ${p.weeks}-week professional programme</p></div>${body}`,
            footer: `<button class="btn btn-ghost" data-close>Close</button><button class="btn btn-outline" id="pdShare"><i class="fa-solid fa-share-nodes"></i> Share</button><a class="btn btn-primary" href="${UI.url("pages/application.html?programme=" + p.id)}">Apply for this programme <i class="fa-solid fa-arrow-right"></i></a>`,
            onOpen: (api) => { api.body.style.padding = "0"; setTimeout(() => UI.animateAll(api.el), 50); }
        });
        UI.$("#pdShare", m.el).onclick = () => UI.copy(location.origin + location.pathname.replace(/[^/]*$/, "") + `programmes.html?id=${p.id}`);
    }

    return { all, active, get, name, tracks, seats, card, bindCards, openDetail };
})();

/* ---------------- Public: Programmes catalogue ---------------- */
Pages["programmes"] = function () {
    const grid = UI.$("#progGrid"), search = UI.$("#progSearch"), sort = UI.$("#progSort");
    let track = "All";
    UI.$("#trackTabs").innerHTML = ["All", ...Programmes.tracks()].map((t) => `<button class="tab ${t === "All" ? "active" : ""}" data-track="${t}">${t}</button>`).join("");
    function render() {
        const q = search.value.toLowerCase();
        let list = Programmes.active().filter((p) => (track === "All" || p.track === track) && (p.name + p.overview + p.modules.join(" ")).toLowerCase().includes(q));
        if (sort.value === "fee-asc") list.sort((a, b) => a.fee - b.fee);
        if (sort.value === "fee-desc") list.sort((a, b) => b.fee - a.fee);
        if (sort.value === "weeks") list.sort((a, b) => a.weeks - b.weeks);
        UI.$("#progCount").textContent = `${list.length} programme${list.length === 1 ? "" : "s"}`;
        grid.innerHTML = list.length ? list.map(Programmes.card).join("") : `<div style="grid-column:1/-1">${UI.empty({ icon: "fa-magnifying-glass", title: "No programmes match your search", text: "Try a different keyword or browse all tracks.", action: `<button class="btn btn-soft" id="clearProg">Clear filters</button>` })}</div>`;
        Programmes.bindCards(grid);
        UI.$("#clearProg")?.addEventListener("click", () => { search.value = ""; track = "All"; UI.$$("#trackTabs .tab").forEach((x) => x.classList.toggle("active", x.dataset.track === "All")); render(); });
        UI.animateAll(grid);
    }
    UI.$$("#trackTabs .tab").forEach((b) => b.addEventListener("click", () => { track = b.dataset.track; UI.$$("#trackTabs .tab").forEach((x) => x.classList.toggle("active", x === b)); render(); }));
    search.addEventListener("input", UI.debounce(render, 150));
    sort.addEventListener("change", render);
    render();
    const id = UI.param("id");
    if (id) setTimeout(() => Programmes.openDetail(id), 300);
};

/* ---------------- Staff: Programme management ---------------- */
Pages["staff-programmes"] = function (view) {
    view.innerHTML = `
        <div class="view-head"><div><h2>Programmes</h2><p>Manage the catalogue, fees, duration, capacity and availability.</p></div>
            <div class="actions"><button class="btn btn-outline" id="exportProg"><i class="fa-solid fa-file-csv"></i> Export</button><button class="btn btn-primary" id="addProg"><i class="fa-solid fa-plus"></i> Add programme</button></div></div>
        <div class="kpis" id="progKpis"></div>
        <div class="panel"><div class="table-tools"><div class="input-icon"><i class="fa-solid fa-magnifying-glass"></i><input class="input" id="pSearch" placeholder="Search programmes…" aria-label="Search programmes"></div>
            <select class="select" id="pStatus" aria-label="Filter by status"><option value="">All statuses</option><option>Active</option><option>Inactive</option></select><span class="spacer"></span></div>
            <div id="progTable"></div></div>`;

    function kpis() {
        const list = Programmes.all();
        const seatData = list.map(Programmes.seats);
        const enrolled = seatData.reduce((a, s) => a + s.enrolled, 0), cap = seatData.reduce((a, s) => a + s.capacity, 0);
        UI.$("#progKpis").innerHTML = [
            ["Total programmes", list.length, "fa-layer-group", ""],
            ["Active programmes", list.filter((p) => p.status === "Active").length, "fa-circle-check", "green"],
            ["Seats filled", `${enrolled} / ${cap}`, "fa-chair", "cyan"],
            ["Average fee", UI.naira(list.reduce((a, p) => a + p.fee, 0) / list.length), "fa-naira-sign", "gold"]
        ].map(([l, v, i, c]) => `<div class="kpi"><div class="kpi-top"><p class="label">${l}</p><span class="icon-tile ${c}"><i class="fa-solid ${i}"></i></span></div><div class="value">${v}</div></div>`).join("");
    }
    const table = UI.dataTable("#progTable", {
        pageSize: 12, onRowClick: (id) => edit(id), onRender: () => bindRow(),
        columns: [
            { key: "name", label: "Programme", render: (p) => `<div class="person"><span class="icon-tile" style="width:38px;height:38px;border-radius:11px;background:${p.color};color:#fff;font-size:.85rem"><i class="fa-solid ${p.icon}"></i></span><div><strong>${UI.esc(p.name)}</strong><small>${p.code} · ${p.track}</small></div></div>` },
            { key: "weeks", label: "Duration", render: (p) => `${p.weeks} weeks` },
            { key: "enrolled", label: "Enrolled", cls: "num", sortValue: (p) => Programmes.seats(p).enrolled, render: (p) => Programmes.seats(p).enrolled },
            { key: "capacity", label: "Capacity", cls: "num" },
            { key: "available", label: "Available", sortable: false, render: (p) => { const s = Programmes.seats(p); return `<div style="min-width:120px"><div class="flex between small"><b>${s.available}</b><span class="muted">${s.pct}%</span></div><div class="progress sm ${s.pct > 85 ? "gold" : ""}"><span style="width:${s.pct}%"></span></div></div>`; } },
            { key: "fee", label: "Fee", cls: "num", render: (p) => `<b>${UI.naira(p.fee)}</b>` },
            { key: "status", label: "Status", render: (p) => UI.badge(p.status) },
            { key: "", label: "", sortable: false, render: (p) => `<div class="row-actions"><button class="icon-btn" data-edit="${p.id}" aria-label="Edit"><i class="fa-solid fa-pen"></i></button><button class="icon-btn ${p.status === "Active" ? "danger" : "success"}" data-toggle="${p.id}" aria-label="${p.status === "Active" ? "Deactivate" : "Activate"}" title="${p.status === "Active" ? "Deactivate" : "Activate"}"><i class="fa-solid ${p.status === "Active" ? "fa-power-off" : "fa-play"}"></i></button></div>` }
        ],
        mobile: (p) => { const s = Programmes.seats(p); return `<div class="m-row"><strong>${UI.esc(p.name)}</strong>${UI.badge(p.status)}</div><div class="m-row"><span>Fee · Duration</span><span>${UI.naira(p.fee)} · ${p.weeks} wks</span></div><div class="m-row"><span>Enrolled / Capacity</span><span>${s.enrolled} / ${s.capacity}</span></div><div class="m-row"><span></span><span class="row-actions"><button class="btn btn-xs btn-soft" data-edit="${p.id}">Edit</button><button class="btn btn-xs btn-ghost" data-toggle="${p.id}">${p.status === "Active" ? "Deactivate" : "Activate"}</button></span></div>`; }
    });
    function refresh() {
        const q = UI.$("#pSearch").value.toLowerCase(), st = UI.$("#pStatus").value;
        table.update(Programmes.all().filter((p) => (!st || p.status === st) && (p.name + p.code + p.track).toLowerCase().includes(q)), { resetPage: false });
        kpis();
    }
    function bindRow() {
        UI.$$("[data-edit]", view).forEach((b) => b.onclick = (e) => { e.stopPropagation(); edit(b.dataset.edit); });
        UI.$$("[data-toggle]", view).forEach((b) => b.onclick = async (e) => {
            e.stopPropagation();
            const p = Programmes.get(b.dataset.toggle);
            const deactivate = p.status === "Active";
            const ok = await UI.confirm({ title: `${deactivate ? "Deactivate" : "Activate"} programme?`, message: deactivate ? `${UI.esc(p.name)} will be hidden from the public website and application form.` : `${UI.esc(p.name)} will be visible to applicants again.`, confirmText: deactivate ? "Deactivate" : "Activate", tone: deactivate ? "danger" : "primary", icon: "fa-power-off" });
            if (!ok) return;
            DB.update("programmes", p.id, { status: deactivate ? "Inactive" : "Active" });
            UI.toast(`Programme ${deactivate ? "deactivated" : "activated"}`, p.name, "success");
            refresh();
        });
    }
    function edit(id) {
        const p = id ? Programmes.get(id) : { name: "", code: "TSCE-", weeks: 8, fee: 50000, capacity: 30, track: "Software", status: "Active", instructor: "", overview: "", modules: [] };
        const m = UI.modal({
            title: id ? "Edit programme" : "Add programme", subtitle: id ? UI.esc(p.code) : "Create a new programme in the catalogue", size: "lg",
            body: `<form id="progForm" class="form-grid" novalidate>
                <div class="field span-2"><label for="f_name">Programme name <span class="req">*</span></label><input id="f_name" name="name" class="input" required value="${UI.esc(p.name)}"></div>
                <div class="field"><label for="f_code">Code <span class="req">*</span></label><input id="f_code" name="code" class="input" required value="${UI.esc(p.code)}"></div>
                <div class="field"><label for="f_track">Track</label><input id="f_track" name="track" class="input" list="trackList" value="${UI.esc(p.track)}"><datalist id="trackList">${Programmes.tracks().map((t) => `<option>${t}</option>`).join("")}</datalist></div>
                <div class="field"><label for="f_fee">Fee (₦) <span class="req">*</span></label><input id="f_fee" name="fee" type="number" min="0" step="500" class="input" required value="${p.fee}"></div>
                <div class="field"><label for="f_weeks">Duration (weeks) <span class="req">*</span></label><input id="f_weeks" name="weeks" type="number" min="1" max="52" class="input" required value="${p.weeks}"></div>
                <div class="field"><label for="f_cap">Capacity <span class="req">*</span></label><input id="f_cap" name="capacity" type="number" min="1" class="input" required value="${p.capacity}"></div>
                <div class="field"><label for="f_status">Status</label><select id="f_status" name="status" class="select"><option ${p.status === "Active" ? "selected" : ""}>Active</option><option ${p.status === "Inactive" ? "selected" : ""}>Inactive</option></select></div>
                <div class="field span-2"><label for="f_inst">Lead instructor</label><input id="f_inst" name="instructor" class="input" value="${UI.esc(p.instructor)}"></div>
                <div class="field span-2"><label for="f_over">Overview</label><textarea id="f_over" name="overview" class="textarea">${UI.esc(p.overview)}</textarea></div>
                <div class="field span-2"><label for="f_mods">Curriculum modules (one per line)</label><textarea id="f_mods" name="modules" class="textarea" style="min-height:140px">${UI.esc(p.modules.join("\n"))}</textarea></div>
                ${id && TSCE_FLYER && PROGRAMME_CATALOGUE.find((x) => x.id === id) ? `<div class="span-2 alert warning"><i class="fa-solid fa-triangle-exclamation"></i><p>Fee and duration for this programme come from the official TSCE flyer. Changes here are logged and apply to <b>new</b> applications only.</p></div>` : ""}
            </form>`,
            footer: `<button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-primary" id="saveProg"><i class="fa-solid fa-floppy-disk"></i> Save programme</button>`
        });
        UI.liveValidate(UI.$("#progForm", m.el));
        UI.$("#saveProg", m.el).onclick = () => {
            const f = UI.$("#progForm", m.el);
            if (!UI.validate(f)) return;
            const d = UI.formData(f);
            const patch = { name: d.name, code: d.code, track: d.track || "General", fee: +d.fee, weeks: +d.weeks, capacity: +d.capacity, status: d.status, instructor: d.instructor, overview: d.overview, modules: d.modules.split("\n").map((x) => x.trim()).filter(Boolean) };
            if (id) DB.update("programmes", id, patch);
            else {
                const newId = d.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 30) + "-" + Date.now().toString(36).slice(-3);
                DB.insert("programmes", { id: newId, ...patch, category: TSCE_FLYER.category, icon: "fa-laptop-code", color: "#1846D6", colorBg: "#EEF3FF", enrolled: 0, outcomes: ["Practical, project-based skills"], audience: ["Anyone interested in this field"], careers: ["Industry roles in " + (d.track || "technology")], requirements: ["Basic computer literacy"], schedules: ["Weekday Morning (9:00am – 12:00pm)", "Weekend (Sat & Sun, 10:00am – 3:00pm)"], createdAt: new Date().toISOString() }, { prepend: false });
            }
            m.close();
            UI.toast(id ? "Programme updated" : "Programme added", d.name, "success");
            refresh();
        };
    }
    UI.$("#pSearch").addEventListener("input", UI.debounce(refresh, 150));
    UI.$("#pStatus").addEventListener("change", refresh);
    UI.$("#addProg").onclick = () => edit(null);
    UI.$("#exportProg").onclick = () => UI.downloadCSV("tsce-programmes.csv", Programmes.all().map((p) => { const s = Programmes.seats(p); return { Code: p.code, Programme: p.name, Track: p.track, Weeks: p.weeks, Fee: p.fee, Enrolled: s.enrolled, Capacity: s.capacity, Available: s.available, Status: p.status }; }));
    refresh();
    const open = UI.param("id"); if (open && Programmes.get(open)) edit(open);
};
