/* ==========================================================================
   TSCE — UI toolkit
   Reusable helpers: formatting, badges, toast, modal, drawer, confirm,
   data tables, empty states, validation, counters, CSV/print, logo.
   ========================================================================== */

const UI = (() => {
    const $ = (sel, root = document) => root.querySelector(sel);
    const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

    /* ---------- Paths ---------- */
    const root = () => (document.body && document.body.dataset.root) || "";
    const url = (p) => root() + p;
    const param = (name) => new URLSearchParams(location.search).get(name);

    /* ---------- Formatting ---------- */
    const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const naira = (n, { compact = false } = {}) => {
        const v = Number(n) || 0;
        if (compact && Math.abs(v) >= 1e6) return "₦" + (v / 1e6).toFixed(v % 1e6 === 0 ? 0 : 2).replace(/\.?0+$/, "") + "m";
        if (compact && Math.abs(v) >= 1e3) return "₦" + (v / 1e3).toFixed(0) + "k";
        return "₦" + v.toLocaleString("en-NG", { maximumFractionDigits: 0 });
    };
    const num = (n) => (Number(n) || 0).toLocaleString("en-NG");
    const date = (d, opts = { day: "numeric", month: "short", year: "numeric" }) => d ? new Date(d).toLocaleDateString("en-GB", opts) : "—";
    const dateLong = (d) => date(d, { weekday: "long", day: "numeric", month: "long", year: "numeric" });
    const dateTime = (d) => d ? `${date(d)}, ${new Date(d).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" })}` : "—";
    function timeAgo(d) {
        const s = (Date.now() - new Date(d)) / 1000;
        if (s < 60) return "just now";
        if (s < 3600) return `${Math.floor(s / 60)}m ago`;
        if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
        if (s < 86400 * 7) return `${Math.floor(s / 86400)}d ago`;
        return date(d);
    }
    const initials = (name = "") => name.replace(/^(Dr|Engr|Mr|Mrs|Mal|Hajiya|Alhaji)\.?\s+/i, "").split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
    const AVATAR_GRADS = ["linear-gradient(135deg,#1846D6,#0EA5E9)", "linear-gradient(135deg,#7C3AED,#1846D6)", "linear-gradient(135deg,#0891B2,#06C8E0)", "linear-gradient(135deg,#12A150,#0EA5E9)", "linear-gradient(135deg,#F59E0B,#E5304B)", "linear-gradient(135deg,#0B1D55,#1846D6)", "linear-gradient(135deg,#DC2F45,#F97316)"];
    function avatar(name, cls = "") {
        const h = [...String(name)].reduce((a, c) => a + c.charCodeAt(0), 0);
        return `<span class="avatar ${cls}" style="background:${AVATAR_GRADS[h % AVATAR_GRADS.length]}" aria-hidden="true">${esc(initials(name))}</span>`;
    }

    /* ---------- Status badges ---------- */
    const BADGE_MAP = {
        success: ["paid", "success", "enrolled", "accepted", "approved", "active", "published", "present", "issued", "verified", "completed", "resolved", "eligible", "applied"],
        warning: ["pending", "under review", "late", "draft", "open", "on leave", "pending payment", "in review", "processing", "requested"],
        danger: ["rejected", "failed", "absent", "inactive", "suspended", "unpaid", "declined", "cancelled", "not eligible"],
        info: ["refunded", "in progress", "submitted", "scheduled"],
        neutral: ["not issued", "none", "closed", "archived"]
    };
    function badge(status, extra = "") {
        const s = String(status || "—");
        const k = s.toLowerCase();
        const tone = Object.keys(BADGE_MAP).find((t) => BADGE_MAP[t].includes(k)) || "primary";
        return `<span class="badge badge-${tone} ${extra}">${esc(s)}</span>`;
    }

    /* ---------- Logo (official TSCE artwork in /assets/logo) ----------
       Absolute URLs so the images also resolve inside print windows. */
    const asset = (p) => new URL(root() + p, location.href).href;
    const logo = (cls = "brand-mark") => `<img class="${cls}" src="${asset("assets/logo/tsce-emblem.png")}" alt="TSCE emblem" width="44" height="44">`;
    const logoFull = (cls = "logo-full") => `<img class="${cls}" src="${asset("assets/logo/tsce-logo-full.png")}" alt="TSCE — Trust Skills Acquisition Centre of Excellence, Zaria">`;
    const brand = (href = url("index.html")) => `<a class="brand" href="${href}" aria-label="Trust Skills Center of Excellence — home">${logo()}<span class="brand-text"><strong>Trust Skills</strong><small>Center of Excellence</small></span></a>`;

    /* ---------- Toasts ---------- */
    function toast(title, message = "", type = "info", ms = 4200) {
        let wrap = $(".toast-wrap");
        if (!wrap) { wrap = document.createElement("div"); wrap.className = "toast-wrap"; wrap.setAttribute("aria-live", "polite"); document.body.appendChild(wrap); }
        const icons = { success: "fa-check", error: "fa-xmark", warning: "fa-exclamation", info: "fa-info" };
        const el = document.createElement("div");
        el.className = `toast ${type}`;
        el.setAttribute("role", type === "error" ? "alert" : "status");
        el.innerHTML = `<span class="t-icon"><i class="fa-solid ${icons[type] || icons.info}"></i></span><div><strong>${esc(title)}</strong>${message ? `<span>${esc(message)}</span>` : ""}</div>`;
        wrap.appendChild(el);
        const kill = () => { el.classList.add("leaving"); setTimeout(() => el.remove(), 260); };
        setTimeout(kill, ms);
        el.addEventListener("click", kill);
    }

    /* ---------- Focus trap for overlays ---------- */
    function trapFocus(container, onEscape) {
        const prev = document.activeElement;
        const focusables = () => $$('a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])', container).filter((e) => e.offsetParent !== null);
        function onKey(e) {
            if (e.key === "Escape") { onEscape && onEscape(); }
            if (e.key !== "Tab") return;
            const f = focusables(); if (!f.length) return;
            const a = f[0], z = f[f.length - 1];
            if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
            else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
        }
        container.addEventListener("keydown", onKey);
        setTimeout(() => { const f = focusables(); (f.find((x) => !x.classList.contains("modal-close")) || f[0])?.focus(); }, 60);
        return () => { container.removeEventListener("keydown", onKey); prev && prev.focus && prev.focus(); };
    }

    /* ---------- Modal ---------- */
    function modal({ title = "", subtitle = "", body = "", footer = "", size = "", onOpen, onClose, dismissible = true, bare = false } = {}) {
        const back = document.createElement("div");
        back.className = "modal-backdrop";
        const id = "m" + Math.random().toString(36).slice(2, 8);
        back.innerHTML = `<div class="modal ${size}" role="dialog" aria-modal="true" ${title ? `aria-labelledby="${id}"` : ""}>
            ${bare ? "" : `<div class="modal-head"><div><h3 id="${id}">${title}</h3>${subtitle ? `<p>${subtitle}</p>` : ""}</div>${dismissible ? `<button class="modal-close" aria-label="Close dialog"><i class="fa-solid fa-xmark"></i></button>` : ""}</div>`}
            <div class="modal-body">${body}</div>
            ${footer ? `<div class="modal-foot">${footer}</div>` : ""}
        </div>`;
        document.body.appendChild(back);
        document.body.style.overflow = "hidden";
        requestAnimationFrame(() => back.classList.add("open"));
        let released;
        const api = {
            el: back, body: $(".modal-body", back), foot: $(".modal-foot", back),
            close() {
                back.classList.remove("open");
                released && released();
                setTimeout(() => { back.remove(); if (!$(".modal-backdrop") && !$(".drawer.open")) document.body.style.overflow = ""; }, 230);
                onClose && onClose();
            },
            setBody(html) { api.body.innerHTML = html; },
            setFooter(html) { if (api.foot) api.foot.innerHTML = html; }
        };
        released = trapFocus(back, dismissible ? api.close : null);
        if (dismissible) {
            back.addEventListener("mousedown", (e) => { if (e.target === back) api.close(); });
            $(".modal-close", back)?.addEventListener("click", api.close);
        }
        $$("[data-close]", back).forEach((b) => b.addEventListener("click", api.close));
        onOpen && onOpen(api);
        return api;
    }

    function confirm({ title = "Are you sure?", message = "", confirmText = "Confirm", cancelText = "Cancel", tone = "primary", icon = "fa-circle-question" } = {}) {
        return new Promise((resolve) => {
            let done = false;
            const m = modal({
                size: "sm", bare: true,
                body: `<div style="text-align:center;padding:10px 4px 0">
                    <div class="icon-tile ${tone === "danger" ? "red" : ""}" style="margin:0 auto 14px;width:56px;height:56px;border-radius:18px;font-size:1.3rem"><i class="fa-solid ${icon}"></i></div>
                    <h3 style="margin-bottom:6px">${title}</h3><p class="muted" style="margin:0">${message}</p></div>`,
                footer: `<button class="btn btn-ghost" data-act="no">${cancelText}</button><button class="btn ${tone === "danger" ? "btn-danger" : "btn-primary"}" data-act="yes">${confirmText}</button>`,
                onClose: () => { if (!done) resolve(false); }
            });
            m.el.querySelector('[data-act="yes"]').onclick = () => { done = true; resolve(true); m.close(); };
            m.el.querySelector('[data-act="no"]').onclick = () => { done = true; resolve(false); m.close(); };
        });
    }

    /* ---------- Drawer (detail side panel) ---------- */
    function drawer({ title = "", subtitle = "", body = "", footer = "", onOpen } = {}) {
        const d = document.createElement("div");
        d.className = "drawer";
        d.innerHTML = `<div class="dr-backdrop"></div><aside class="dr-panel" role="dialog" aria-modal="true" aria-label="${esc(title.replace(/<[^>]+>/g, ""))}">
            <div class="dr-head"><div><h3>${title}</h3>${subtitle ? `<div class="muted small mt-1">${subtitle}</div>` : ""}</div><button class="modal-close" aria-label="Close panel"><i class="fa-solid fa-xmark"></i></button></div>
            <div class="dr-body">${body}</div>${footer ? `<div class="dr-foot">${footer}</div>` : ""}</aside>`;
        document.body.appendChild(d);
        document.body.style.overflow = "hidden";
        requestAnimationFrame(() => d.classList.add("open"));
        let released;
        const api = {
            el: d, body: $(".dr-body", d), foot: $(".dr-foot", d),
            close() { d.classList.remove("open"); released && released(); setTimeout(() => { d.remove(); if (!$(".modal-backdrop") && !$(".drawer.open")) document.body.style.overflow = ""; }, 320); },
            setBody(html) { api.body.innerHTML = html; },
            setFooter(html) { if (api.foot) api.foot.innerHTML = html; }
        };
        released = trapFocus(d, api.close);
        $(".dr-backdrop", d).onclick = api.close;
        $(".modal-close", d).onclick = api.close;
        onOpen && onOpen(api);
        return api;
    }

    /* ---------- Empty state ---------- */
    const empty = ({ icon = "fa-folder-open", title = "Nothing here yet", text = "", action = "" } = {}) =>
        `<div class="empty"><div class="empty-icon"><i class="fa-solid ${icon}"></i></div><h4>${title}</h4>${text ? `<p>${text}</p>` : ""}${action}</div>`;

    /* ---------- Data table (sorting, paging, mobile card view) ---------- */
    function dataTable(container, { columns, rows = [], pageSize = 10, empty: emptyCfg, onRowClick, rowId = (r) => r.id, mobile, onRender } = {}) {
        let data = rows, page = 1, sortKey = null, sortDir = 1;
        const el = typeof container === "string" ? $(container) : container;

        function sorted() {
            if (!sortKey) return data;
            const col = columns.find((c) => c.key === sortKey);
            const val = col.sortValue || ((r) => r[col.key]);
            return [...data].sort((a, b) => { const x = val(a), y = val(b); return (x > y ? 1 : x < y ? -1 : 0) * sortDir; });
        }
        function render() {
            const list = sorted();
            const pages = Math.max(1, Math.ceil(list.length / pageSize));
            page = Math.min(page, pages);
            const slice = list.slice((page - 1) * pageSize, page * pageSize);
            if (!list.length) { el.innerHTML = empty(emptyCfg || { icon: "fa-inbox", title: "No records found", text: "Try adjusting your search or filters." }); return; }
            const head = columns.map((c) => `<th scope="col" class="${c.sortable !== false && c.key ? "sortable" : ""} ${c.cls || ""}" data-key="${c.key || ""}">${c.label}${c.sortable !== false && c.key ? `<i class="fa-solid ${sortKey === c.key ? (sortDir > 0 ? "fa-arrow-up" : "fa-arrow-down") : "fa-sort"} sort-ic"></i>` : ""}</th>`).join("");
            const body = slice.map((r) => `<tr class="${onRowClick ? "clickable" : ""}" data-id="${esc(rowId(r))}" ${onRowClick ? 'tabindex="0"' : ""}>${columns.map((c) => `<td class="${c.cls || ""}">${c.render ? c.render(r) : esc(r[c.key])}</td>`).join("")}</tr>`).join("");
            const mob = slice.map((r) => `<div class="m-card ${onRowClick ? "clickable" : ""}" data-id="${esc(rowId(r))}">${mobile ? mobile(r) : columns.filter((c) => c.label).slice(0, 5).map((c) => `<div class="m-row"><span>${c.label}</span><span>${c.render ? c.render(r) : esc(r[c.key])}</span></div>`).join("")}</div>`).join("");
            const from = (page - 1) * pageSize + 1, to = Math.min(page * pageSize, list.length);
            let pager = "";
            if (pages > 1) {
                pager = `<div class="pager"><button data-pg="${page - 1}" ${page === 1 ? "disabled" : ""} aria-label="Previous page"><i class="fa-solid fa-chevron-left"></i></button>`;
                for (let i = 1; i <= pages; i++) if (i === 1 || i === pages || Math.abs(i - page) <= 1) pager += `<button data-pg="${i}" class="${i === page ? "active" : ""}">${i}</button>`; else if (Math.abs(i - page) === 2) pager += `<button disabled>…</button>`;
                pager += `<button data-pg="${page + 1}" ${page === pages ? "disabled" : ""} aria-label="Next page"><i class="fa-solid fa-chevron-right"></i></button></div>`;
            }
            el.innerHTML = `<div class="table-wrap responsive"><table class="table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table><div class="m-list">${mob}</div></div>
                <div class="table-foot"><span>Showing <b>${from}–${to}</b> of <b>${list.length}</b></span>${pager}</div>`;
            $$("th.sortable", el).forEach((th) => th.onclick = () => { const k = th.dataset.key; sortDir = sortKey === k ? -sortDir : 1; sortKey = k; render(); });
            $$("[data-pg]", el).forEach((b) => b.onclick = () => { page = +b.dataset.pg; render(); });
            if (onRowClick) {
                $$("tr[data-id], .m-card[data-id]", el).forEach((tr) => {
                    tr.addEventListener("click", (e) => { if (e.target.closest("button, a, input, select")) return; onRowClick(tr.dataset.id); });
                    tr.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target === tr) onRowClick(tr.dataset.id); });
                });
            }
            onRender && onRender(el);
        }
        render();
        return { update(newRows, { resetPage = true } = {}) { data = newRows; if (resetPage) page = 1; render(); }, el };
    }

    /* ---------- Skeleton ---------- */
    const skeleton = (lines = 4) => `<div style="padding:22px;display:grid;gap:12px">${Array.from({ length: lines }, (_, i) => `<div class="skeleton" style="height:${i === 0 ? 22 : 14}px;width:${[60, 100, 90, 75, 95][i % 5]}%"></div>`).join("")}</div>`;
    function withSkeleton(el, renderFn, ms = 280) {
        el.innerHTML = skeleton(5);
        setTimeout(renderFn, ms);
    }

    /* ---------- Forms & validation ---------- */
    function formData(form) {
        const o = {};
        new FormData(form).forEach((v, k) => { o[k] = typeof v === "string" ? v.trim() : v; });
        return o;
    }
    function fieldError(input, msg) {
        const field = input.closest(".field");
        if (!field) return;
        let err = $(".field-error", field);
        if (!err) { err = document.createElement("span"); err.className = "field-error"; field.appendChild(err); }
        err.textContent = msg || "";
        field.classList.toggle("has-error", !!msg);
        input.setAttribute("aria-invalid", msg ? "true" : "false");
        if (msg) { err.id = err.id || "err" + Math.random().toString(36).slice(2, 7); input.setAttribute("aria-describedby", err.id); }
    }
    function validateInput(input) {
        const v = (input.value || "").trim();
        const label = input.closest(".field")?.querySelector("label")?.textContent.replace("*", "").trim() || "This field";
        if (input.required && !v && input.type !== "checkbox") return `${label} is required.`;
        if (input.type === "checkbox" && input.required && !input.checked) return "Please confirm to continue.";
        if (!v) return "";
        if (input.type === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v)) return "Enter a valid email address.";
        if (input.dataset.type === "phone" && !/^(\+?234|0)[789][01]\d{8}$/.test(v.replace(/[\s-]/g, ""))) return "Enter a valid Nigerian phone number (e.g. 0803 123 4567).";
        if (input.minLength > 0 && v.length < input.minLength) return `${label} must be at least ${input.minLength} characters.`;
        if (input.type === "number") {
            if (input.min !== "" && +v < +input.min) return `Minimum value is ${input.min}.`;
            if (input.max !== "" && +v > +input.max) return `Maximum value is ${input.max}.`;
        }
        if (input.dataset.match) { const other = document.getElementById(input.dataset.match); if (other && other.value !== input.value) return "Passwords do not match."; }
        return "";
    }
    function validate(scope) {
        let firstBad = null;
        $$("input, select, textarea", scope).forEach((inp) => {
            if (inp.disabled || inp.type === "hidden" || inp.offsetParent === null) return;
            const msg = validateInput(inp);
            fieldError(inp, msg);
            if (msg && !firstBad) firstBad = inp;
        });
        if (firstBad) { firstBad.focus(); return false; }
        return true;
    }
    function liveValidate(scope) {
        scope.addEventListener("blur", (e) => { if (e.target.matches("input, select, textarea")) fieldError(e.target, validateInput(e.target)); }, true);
        scope.addEventListener("input", (e) => { const f = e.target.closest(".field"); if (f && f.classList.contains("has-error")) fieldError(e.target, validateInput(e.target)); });
    }

    /* ---------- Animations ---------- */
    function animateCount(el) {
        const target = parseFloat(el.dataset.count);
        const prefix = el.dataset.prefix || "", suffix = el.dataset.suffix || "";
        const dur = 1400, t0 = performance.now();
        const fmt = (v) => el.dataset.format === "naira" ? naira(v) : Math.round(v).toLocaleString("en-NG");
        function tick(t) {
            const p = Math.min(1, (t - t0) / dur);
            const eased = 1 - Math.pow(1 - p, 3);
            el.textContent = prefix + fmt(target * eased) + suffix;
            if (p < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
    }
    function observe(selector, fn, rootEl = document) {
        const els = $$(selector, rootEl);
        if (!("IntersectionObserver" in window)) { els.forEach(fn); return; }
        const io = new IntersectionObserver((entries) => entries.forEach((en) => { if (en.isIntersecting) { fn(en.target); io.unobserve(en.target); } }), { threshold: .2 });
        els.forEach((e) => io.observe(e));
    }
    const counters = (rootEl) => observe("[data-count]", animateCount, rootEl);
    const reveal = (rootEl) => observe(".reveal", (e) => e.classList.add("in"), rootEl);
    const progressBars = (rootEl) => observe(".progress > span[data-value]", (e) => { e.style.width = Math.min(100, +e.dataset.value) + "%"; }, rootEl);
    function animateAll(rootEl = document) { counters(rootEl); reveal(rootEl); progressBars(rootEl); rings(rootEl); }

    /* Ring progress (SVG) */
    function ring(pct, label = "", cls = "") {
        const r = 52, c = 2 * Math.PI * r;
        return `<div class="ring ${cls}" data-ring="${pct}"><svg viewBox="0 0 124 124"><defs><linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1846D6"/><stop offset="1" stop-color="#06C8E0"/></linearGradient></defs>
            <circle class="bg" cx="62" cy="62" r="${r}"/><circle class="fg" cx="62" cy="62" r="${r}" stroke-dasharray="${c}" stroke-dashoffset="${c}"/></svg>
            <div class="ring-label"><div><strong>${Math.round(pct)}%</strong><small>${label}</small></div></div></div>`;
    }
    const rings = (rootEl) => observe("[data-ring]", (el) => { const c = el.querySelector(".fg"); const len = 2 * Math.PI * 52; c.style.strokeDashoffset = len * (1 - (+el.dataset.ring) / 100); }, rootEl);

    function confetti() {
        const box = document.createElement("div");
        box.className = "confetti";
        const colors = ["#1846D6", "#06C8E0", "#F5B400", "#17A34A", "#E5304B", "#0EA5E9"];
        for (let i = 0; i < 90; i++) {
            const p = document.createElement("i");
            p.style.left = Math.random() * 100 + "vw";
            p.style.background = colors[i % colors.length];
            p.style.animationDuration = 1.8 + Math.random() * 1.8 + "s";
            p.style.animationDelay = Math.random() * .4 + "s";
            p.style.transform = `rotate(${Math.random() * 360}deg)`;
            box.appendChild(p);
        }
        document.body.appendChild(box);
        setTimeout(() => box.remove(), 4200);
    }

    /* ---------- Export / print ---------- */
    function downloadCSV(filename, rows) {
        if (!rows.length) { toast("Nothing to export", "There are no records in this view.", "warning"); return; }
        const cols = Object.keys(rows[0]);
        const q = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
        const csv = [cols.map(q).join(","), ...rows.map((r) => cols.map((c) => q(r[c])).join(","))].join("\r\n");
        const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 1000);
        toast("Export ready", `${filename} downloaded (${rows.length} rows).`, "success");
    }
    function printHTML(title, html) {
        const w = window.open("", "_blank", "width=900,height=1000");
        if (!w) { toast("Pop-up blocked", "Allow pop-ups to print this document.", "warning"); return; }
        const base = location.href.replace(/[^/]*$/, "") + root();
        w.document.write(`<!doctype html><html><head><title>${esc(title)}</title><base href="${base}">
            <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap">
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
            <link rel="stylesheet" href="css/main.css"><link rel="stylesheet" href="css/dashboard.css">
            <style>body{padding:32px;background:#fff}.no-print{display:none!important}</style></head><body>${html}
            <script>window.onload=function(){setTimeout(function(){window.print()},450)}<\/script></body></html>`);
        w.document.close();
    }

    const copy = (text) => {
        (navigator.clipboard ? navigator.clipboard.writeText(text) : Promise.reject()).then(() => toast("Copied", text, "success", 2200)).catch(() => toast("Copy failed", "Please copy manually.", "warning"));
    };
    const debounce = (fn, ms = 200) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

    /* Friendly error wrapper for page controllers */
    function safe(fn, where = "") {
        try { return fn(); }
        catch (e) {
            console.error("TSCE error", where, e);
            toast("Something went wrong.", "Please check your information and try again.", "error");
        }
    }

    return {
        $, $$, root, url, param, esc, naira, num, date, dateLong, dateTime, timeAgo, initials, avatar, badge, logo, logoFull, brand,
        toast, modal, confirm, drawer, empty, dataTable, skeleton, withSkeleton, formData, validate, liveValidate, fieldError,
        animateAll, counters, reveal, progressBars, ring, rings, confetti, downloadCSV, printHTML, copy, debounce, sleep, safe
    };
})();

/* Page controller registry — each module registers its pages here. */
const Pages = {};
