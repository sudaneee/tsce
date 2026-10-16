/* ==========================================================================
   TSCE — small touches for the server-rendered pages. Presentation only:
   every figure, list and form result is already in the HTML from Django, and
   everything works without this file (it just adds motion and convenience).
   ========================================================================== */
(() => {
    const $ = (s, r = document) => r.querySelector(s);
    const $$ = (s, r = document) => [...r.querySelectorAll(s)];

    /* Reveal-on-scroll, counters and progress bars */
    function observe(els, fn) {
        if (!("IntersectionObserver" in window)) { els.forEach(fn); return; }
        const io = new IntersectionObserver((entries) => entries.forEach((e) => { if (e.isIntersecting) { fn(e.target); io.unobserve(e.target); } }), { threshold: 0.2 });
        els.forEach((e) => io.observe(e));
    }
    observe($$(".reveal"), (el) => el.classList.add("in"));
    observe($$(".progress > span[data-value]"), (el) => { el.style.width = Math.min(100, +el.dataset.value) + "%"; });

    /* Header shadow once the page scrolls */
    const header = $("#siteHeader");
    if (header) { const f = () => header.classList.toggle("scrolled", scrollY > 8); addEventListener("scroll", f, { passive: true }); f(); }

    /* FAQ accordion */
    $$(".faq-item").forEach((item) => {
        const q = item.querySelector(".faq-q");
        q?.addEventListener("click", () => { const open = !item.classList.contains("open"); item.classList.toggle("open", open); q.setAttribute("aria-expanded", open); });
    });

    /* Countdowns (announcement bar + home cohort block) */
    const startOf = (d) => new Date(`${d}T08:00:00`);
    const bar = $("#abCount");
    if (bar?.dataset.start) {
        const t = startOf(bar.dataset.start);
        const f = () => { const ms = t - Date.now(); bar.textContent = ms <= 0 ? "Classes are in session" : `${Math.floor(ms / 864e5)}d ${Math.floor(ms / 36e5) % 24}h to kick-off`; };
        setInterval(f, 60000);
    }
    const cd = $("#countdown");
    if (cd?.dataset.start) {
        const t = startOf(cd.dataset.start), cells = $$("strong", cd);
        const f = () => { const ms = Math.max(0, t - Date.now()); [Math.floor(ms / 864e5), Math.floor(ms / 36e5) % 24, Math.floor(ms / 6e4) % 60, Math.floor(ms / 1e3) % 60].forEach((v, i) => { if (cells[i]) cells[i].textContent = String(v).padStart(2, "0"); }); };
        f(); setInterval(f, 1000);
    }

    /* Career pathway: cycle the highlighted stage once it is on screen */
    const path = $("#pathway");
    if (path) {
        const steps = $$(".path-step", path); let i = 0;
        observe([path], () => { path.classList.add("in"); setInterval(() => { steps.forEach((s, k) => s.classList.toggle("active", k === i)); i = (i + 1) % steps.length; }, 1400); });
    }

    /* Programme catalogue: filter instantly (the links/form also work without JS) */
    const grid = $("#progGrid");
    if (grid) {
        const search = $("#progSearch"), sort = $("#progSort"), count = $("#progCount"), empty = $("#progEmpty");
        let track = $("#trackTabs .tab.active")?.dataset.track || "All";
        const cards = $$(".prog-card", grid);
        const apply = () => {
            const q = (search?.value || "").trim().toLowerCase();
            const shown = cards.filter((c) => { const ok = (track === "All" || c.dataset.track === track) && c.dataset.search.includes(q); c.hidden = !ok; return ok; });
            const key = sort?.value;
            const order = [...shown].sort((a, b) => key === "fee-asc" ? a.dataset.fee - b.dataset.fee : key === "fee-desc" ? b.dataset.fee - a.dataset.fee : key === "weeks" ? a.dataset.weeks - b.dataset.weeks : a.dataset.order - b.dataset.order);
            order.forEach((c) => grid.appendChild(c));
            if (count) count.textContent = `${shown.length} programme${shown.length === 1 ? "" : "s"}`;
            if (empty) empty.hidden = shown.length > 0;
        };
        $$("#trackTabs .tab").forEach((tab) => tab.addEventListener("click", (e) => {
            e.preventDefault(); track = tab.dataset.track;
            $$("#trackTabs .tab").forEach((x) => x.classList.toggle("active", x === tab)); apply();
        }));
        search?.addEventListener("input", apply);
        sort?.addEventListener("change", apply);
        $("#progFilters")?.addEventListener("submit", (e) => { e.preventDefault(); apply(); });
        $("#clearProg")?.addEventListener("click", (e) => { e.preventDefault(); if (search) search.value = ""; track = "All"; $$("#trackTabs .tab").forEach((x) => x.classList.toggle("active", x.dataset.track === "All")); apply(); });
        cards.forEach((c, i) => { c.dataset.order = i; });
    }

    /* Pop-ups opened by #anchor (programme details, news): Esc closes, page doesn't scroll behind */
    // A fragment navigation (not history.replaceState) is what updates :target.
    const closeTarget = () => { if (location.hash && $(location.hash + ".link-modal")) location.replace("#close"); setTimeout(lock, 0); };
    addEventListener("keydown", (e) => { if (e.key === "Escape") { const open = $(".link-modal:target, .link-modal.open"); if (open) { open.classList.remove("open"); closeTarget(); } } });
    const lock = () => { document.body.style.overflow = $(".link-modal:target, .link-modal.open") ? "hidden" : ""; };
    addEventListener("hashchange", lock); lock();
    $$(".link-modal [data-close-modal]").forEach((a) => a.addEventListener("click", () => { a.closest(".link-modal").classList.remove("open"); setTimeout(lock, 0); }));

    /* Copy a share link */
    $$("[data-copy]").forEach((b) => b.addEventListener("click", async (e) => {
        e.preventDefault();
        try { await navigator.clipboard.writeText(new URL(b.dataset.copy, location.href).href); b.innerHTML = '<i class="fa-solid fa-check"></i> Link copied'; } catch (err) { location.href = b.dataset.copy; }
    }));
})();
