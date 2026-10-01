/* ==========================================================================
   TSCE — API client (Django backend)
   --------------------------------------------------------------------------
   The single gateway between the frontend and the server. It replaces the
   localStorage DB in storage.js feature by feature (see PLAN.md).

     const programmes = await API.get("programmes");
     const app = await API.post("applications", formData);   // FormData → multipart
     await API.patch("me/profile", { phone: "0803…" });

   Errors are thrown as API.Error with { status, message, code, fields }.
   Server error bodies look like: { error, code, fields: { name: ["…"] } }.
   ========================================================================== */

const API = (() => {
    const BASE = "/api/";
    const UNSAFE = new Set(["POST", "PUT", "PATCH", "DELETE"]);

    class ApiError extends Error {
        constructor(status, message, { code = "error", fields = {}, data = null } = {}) {
            super(message);
            this.name = "ApiError";
            this.status = status;     // 0 = network failure
            this.code = code;
            this.fields = fields;     // { fieldName: ["message", …] }
            this.data = data;
        }
        get isNetwork() { return this.status === 0; }
        get isAuth() { return this.status === 401 || this.status === 403; }
    }

    function cookie(name) {
        const m = document.cookie.match(new RegExp("(?:^|;\\s*)" + name + "=([^;]*)"));
        return m ? decodeURIComponent(m[1]) : null;
    }

    let csrfReady = null;
    /** Makes sure the csrftoken cookie exists before the first unsafe request. */
    function ensureCsrf() {
        if (cookie("csrftoken")) return Promise.resolve();
        csrfReady = csrfReady || fetch(BASE + "auth/csrf", { credentials: "same-origin" }).then(() => { }, () => { csrfReady = null; });
        return csrfReady;
    }

    function buildUrl(path, query) {
        const url = new URL(BASE + String(path).replace(/^\/+/, ""), location.origin);
        if (query) Object.entries(query).forEach(([k, v]) => {
            if (v === undefined || v === null || v === "") return;
            (Array.isArray(v) ? v : [v]).forEach((x) => url.searchParams.append(k, x));
        });
        return url;
    }

    async function request(method, path, { body, query, signal, headers = {} } = {}) {
        method = method.toUpperCase();
        const opts = { method, credentials: "same-origin", signal, headers: { Accept: "application/json", ...headers } };
        if (body !== undefined) {
            if (body instanceof FormData) opts.body = body;   // browser sets the multipart boundary
            else { opts.body = JSON.stringify(body); opts.headers["Content-Type"] = "application/json"; }
        }
        if (UNSAFE.has(method)) {
            await ensureCsrf();
            opts.headers["X-CSRFToken"] = cookie("csrftoken") || "";
        }

        let res;
        try { res = await fetch(buildUrl(path, query), opts); }
        catch (e) {
            if (e.name === "AbortError") throw e;
            throw new ApiError(0, "We couldn't reach the TSCE server. Check your internet connection and try again.", { code: "network" });
        }

        const isJson = (res.headers.get("Content-Type") || "").includes("application/json");
        const data = res.status === 204 ? null : isJson ? await res.json().catch(() => null) : await res.text();

        if (!res.ok) {
            const fallback = {
                400: "Please check the details you entered.",
                401: "Please sign in to continue.",
                403: "You don't have permission to do that.",
                404: "We couldn't find what you were looking for.",
                413: "That file is too large.",
                429: "Too many attempts. Please wait a moment and try again."
            }[res.status] || "Something went wrong on our side. Please try again.";
            const err = new ApiError(res.status, (data && data.error) || fallback, { code: data?.code, fields: data?.fields || {}, data });
            if (res.status === 401) document.dispatchEvent(new CustomEvent("api:unauthorized", { detail: err }));
            throw err;
        }
        return data;
    }

    /** Puts server field errors next to the matching inputs (name="…") in a form. */
    function showFieldErrors(form, err) {
        if (!(err instanceof ApiError) || !form) return false;
        let shown = false;
        Object.entries(err.fields || {}).forEach(([name, msgs]) => {
            const input = form.querySelector(`[name="${CSS.escape(name)}"]`);
            if (input && typeof UI !== "undefined") { UI.fieldError(input, [].concat(msgs)[0]); shown = true; }
        });
        return shown;
    }

    return {
        Error: ApiError,
        request,
        get: (path, query, opts) => request("GET", path, { ...opts, query }),
        post: (path, body, opts) => request("POST", path, { ...opts, body }),
        put: (path, body, opts) => request("PUT", path, { ...opts, body }),
        patch: (path, body, opts) => request("PATCH", path, { ...opts, body }),
        del: (path, opts) => request("DELETE", path, opts),
        ensureCsrf,
        showFieldErrors
    };
})();

/* ==========================================================================
   Site data every page needs (GET /api/site): public settings + programme
   catalogue. The router loads it once per page; modules then read it
   synchronously (Site.settings, Site.programmes).
   ========================================================================== */
const Site = (() => {
    let data = null;
    async function load() {
        try { data = await API.get("site"); }
        catch (e) { data = null; console.warn("TSCE: couldn't load site data —", e.message); }
        return data;
    }
    /** "2026-10-12" → local midnight (new Date("2026-10-12") would be UTC, i.e. the day before in the Americas). */
    const day = (iso) => iso ? new Date(iso + "T00:00:00") : null;
    return {
        load, day,
        get ready() { return !!data; },
        get settings() { return data ? data.settings : null; },
        get programmes() { return data ? data.programmes : []; },
        get cohortDate() { return data?.settings.admissions.cohortDate || null; }
    };
})();
