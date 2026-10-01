/* ==========================================================================
   TSCE — Storage layer (simulated backend database)
   --------------------------------------------------------------------------
   All records live in localStorage under "tsce_*" keys. Every read/write
   goes through this module, so replacing it with real API calls later
   (e.g. fetch('/api/students')) only requires changing this file.
   Falls back to in-memory storage if localStorage is blocked.
   ========================================================================== */

const DB = (() => {
    const PREFIX = "tsce_";
    const VERSION = "1.0.1";
    const COLLECTIONS = ["users", "students", "applications", "payments", "programmes", "attendance", "results",
        "scholarships", "staff", "announcements", "notifications", "tickets", "enquiries"];
    const memory = {};
    let storageOK = true;

    try { localStorage.setItem(PREFIX + "probe", "1"); localStorage.removeItem(PREFIX + "probe"); }
    catch (e) { storageOK = false; }

    function raw(key) {
        try { return storageOK ? localStorage.getItem(PREFIX + key) : memory[key] ?? null; }
        catch (e) { return memory[key] ?? null; }
    }
    function read(key, fallback = null) {
        const v = raw(key);
        if (v == null) return fallback;
        try { return JSON.parse(v); } catch (e) { return fallback; }
    }
    function write(key, value) {
        const s = JSON.stringify(value);
        try { if (storageOK) localStorage.setItem(PREFIX + key, s); else memory[key] = s; }
        catch (e) { memory[key] = s; console.warn("TSCE storage write failed", e); }
    }

    function seed() {
        const data = SeedData.build();
        COLLECTIONS.forEach((k) => write(k, data[k] || []));
        write("settings", data.settings);
        write("version", VERSION);
    }

    function init() {
        if (read("version") !== VERSION) seed();
    }

    /* ---- Collection helpers ---- */
    const all = (key) => read(key, []);
    const save = (key, rows) => write(key, rows);
    const get = (key, id) => all(key).find((r) => r.id === id) || null;
    const where = (key, pred) => all(key).filter(pred);
    const first = (key, pred) => all(key).find(pred) || null;

    function insert(key, record, { prepend = true } = {}) {
        const rows = all(key);
        prepend ? rows.unshift(record) : rows.push(record);
        save(key, rows);
        return record;
    }
    function update(key, id, patch) {
        const rows = all(key);
        const i = rows.findIndex((r) => r.id === id);
        if (i < 0) return null;
        rows[i] = typeof patch === "function" ? patch({ ...rows[i] }) : { ...rows[i], ...patch };
        save(key, rows);
        return rows[i];
    }
    function remove(key, id) {
        save(key, all(key).filter((r) => r.id !== id));
    }

    /* ---- Settings & sequences ---- */
    const settings = () => read("settings", {});
    function saveSettings(patch) {
        const s = settings();
        Object.keys(patch).forEach((k) => { s[k] = typeof patch[k] === "object" && !Array.isArray(patch[k]) ? { ...(s[k] || {}), ...patch[k] } : patch[k]; });
        write("settings", s);
        return s;
    }
    /** Atomically increments a named counter (app, tx, student) and returns the new value. */
    function next(name) {
        const s = settings();
        s.counters = s.counters || {};
        s.counters[name] = (s.counters[name] || 0) + 1;
        write("settings", s);
        return s.counters[name];
    }

    /* ---- Session (simulated auth token) ---- */
    const session = {
        get: () => read("session"),
        set: (v) => write("session", v),
        clear: () => { try { storageOK ? localStorage.removeItem(PREFIX + "session") : delete memory.session; } catch (e) { delete memory.session; } }
    };

    /* ---- Temporary state (drafts, flow hand-off) ---- */
    const temp = {
        get: (k) => read("tmp_" + k),
        set: (k, v) => write("tmp_" + k, v),
        clear: (k) => { try { storageOK ? localStorage.removeItem(PREFIX + "tmp_" + k) : delete memory["tmp_" + k]; } catch (e) { /* ignore */ } }
    };

    function reset() {
        try {
            Object.keys(localStorage).filter((k) => k.startsWith(PREFIX)).forEach((k) => localStorage.removeItem(k));
        } catch (e) { Object.keys(memory).forEach((k) => delete memory[k]); }
        seed();
    }

    return { init, all, save, get, where, first, insert, update, remove, settings, saveSettings, next, session, temp, reset, persistent: () => storageOK };
})();

DB.init();
