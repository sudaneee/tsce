/* ==========================================================================
   TSCE — Payments
   --------------------------------------------------------------------------
   ┌────────────┐   ┌──────────────────┐   ┌─────────────────────────────┐
   │  UI pages  │ → │  PaymentService  │ → │  gateway (ZainpaySimulator)  │
   └────────────┘   └──────────────────┘   └─────────────────────────────┘
   The UI only ever talks to PaymentService. PaymentService talks to
   `PaymentService.gateway`. To go live, implement the same three methods
   (initializePayment / processPayment / verifyPayment) in a
   `ZainpayServerGateway` that calls YOUR backend, e.g.:
       POST /api/payments/initialize  → backend calls Zainpay with secret key
       GET  /api/payments/verify/:ref → backend verifies with Zainpay
       POST /api/webhooks/zainpay     → backend receives payment notifications
   Zainpay secret keys must NEVER be placed in browser JavaScript.
   ========================================================================== */

/* ---------------- Simulated Zainpay gateway (sandbox behaviour) ---------------- */
const ZainpaySimulator = (() => {
    const config = {
        environment: "sandbox",                              // "sandbox" | "live"
        baseUrl: "https://sandbox.zainpay.ng",                // documented sandbox host (not called)
        merchantName: "Trust Skills Center of Excellence",
        publicKeyHint: "ZP_SANDBOX_PUBLIC_KEY (server-side only in production)"
    };
    const pad = (n, l) => String(n).padStart(l, "0");
    const store = (ref, patch) => { const t = { ...(DB.temp.get("zp_" + ref) || {}), ...patch }; DB.temp.set("zp_" + ref, t); return t; };

    /** TSCE-ZP-YYYYMMDD-000123 */
    function generateTransactionReference() {
        const d = new Date();
        const seq = DB.next("tx");
        return `${DB.settings().payments?.refPrefix || "TSCE-ZP"}-${d.getFullYear()}${pad(d.getMonth() + 1, 2)}${pad(d.getDate(), 2)}-${pad(seq, 6)}`;
    }

    /** Mirrors a gateway "initialize payment" API response. */
    async function initializePayment({ amount, email, name, description, callbackUrl, metadata = {} }) {
        await UI.sleep(450 + Math.random() * 300);
        if (!(amount > 0)) return { code: "04", status: "400 Bad Request", description: "Invalid amount" };
        if (!email) return { code: "04", status: "400 Bad Request", description: "Customer email is required" };
        const txnRef = generateTransactionReference();
        store(txnRef, { txnRef, amount, email, name, description, callbackUrl, metadata, status: "PENDING", createdAt: new Date().toISOString() });
        return { code: "00", status: "200 OK", description: "successful", data: { txnRef, amount, checkoutUrl: `${config.baseUrl}/checkout/${txnRef}` } };
    }

    /**
     * Simulates the customer completing checkout (1.5–2.5s).
     * Sandbox rules: card ending 0002 → declined; outcome "fail" → declined.
     */
    async function processPayment(txnRef, { channel = "card", outcome = "success", card = "" } = {}) {
        await UI.sleep(1500 + Math.random() * 1000);
        const t = DB.temp.get("zp_" + txnRef);
        if (!t) return { code: "44", status: "FAILED", message: "Transaction not found" };
        const declined = outcome === "fail" || /0002$/.test(String(card).replace(/\s/g, ""));
        const status = declined ? "FAILED" : "SUCCESS";
        store(txnRef, { status, channel, processedAt: new Date().toISOString(), failureReason: declined ? "Card declined by issuing bank (51 — insufficient funds)" : null });
        return { code: declined ? "51" : "00", status, message: declined ? "Payment could not be completed." : "Approved" };
    }

    /** Mirrors a gateway "verify transaction" API — always verify before giving value. */
    async function verifyPayment(txnRef) {
        await UI.sleep(350 + Math.random() * 250);
        const t = DB.temp.get("zp_" + txnRef);
        if (!t) return { code: "44", status: "404", description: "Transaction not found" };
        return { code: "00", status: "200 OK", data: { txnRef, amount: t.amount, paymentStatus: t.status, paymentChannel: t.channel, email: t.email, processedAt: t.processedAt, failureReason: t.failureReason } };
    }

    /** Virtual account generation (simulated). */
    async function createVirtualAccount({ name }) {
        await UI.sleep(700);
        const acct = "99" + String(Math.floor(10000000 + Math.random() * 89999999));
        return { code: "00", data: { bankName: "Zainpay MFB (Sandbox)", accountNumber: acct, accountName: `TSCE / ${name}` } };
    }

    return { config, generateTransactionReference, initializePayment, processPayment, verifyPayment, createVirtualAccount };
})();

/* ---------------- Payment service (business logic, gateway-agnostic) ---------------- */
const PaymentService = {
    gateway: ZainpaySimulator,     // ← swap for ZainpayServerGateway when the backend exists

    /**
     * Runs the full checkout: initialize → process → verify → record.
     * onStep(index) lets the UI animate progress. Returns the stored payment record.
     */
    async checkout({ amount, email, name, description, channel, outcome, card, applicationId = null, studentId = null, programmeId = null, fee = amount, discount = 0 }, onStep = () => { }) {
        onStep(0);
        const init = await this.gateway.initializePayment({ amount, email, name, description, metadata: { applicationId, studentId } });
        if (init.code !== "00") throw new Error(init.description || "Unable to initialise payment");
        const ref = init.data.txnRef;
        const base = { id: ref, ref, applicationId, studentId, name, email, programmeId, amount, fee, discount, gateway: "Zainpay", channel, description, createdAt: new Date().toISOString() };
        DB.insert("payments", { ...base, status: "PENDING" });

        onStep(1);
        await this.gateway.processPayment(ref, { channel, outcome, card });

        onStep(2);
        const v = await this.gateway.verifyPayment(ref);
        const status = v.data?.paymentStatus || "FAILED";
        const rec = DB.update("payments", ref, { status, verifiedAt: new Date().toISOString(), failureReason: v.data?.failureReason || null });
        onStep(3);
        await UI.sleep(350);
        return rec;
    },

    async verify(ref) {
        const v = await this.gateway.verifyPayment(ref);
        // Seeded/pending bank transfers without a gateway session: simulate settlement confirmation.
        const status = v.code === "00" ? v.data.paymentStatus : "SUCCESS";
        const finalStatus = status === "PENDING" ? "SUCCESS" : status;
        return DB.update("payments", ref, { status: finalStatus, verifiedAt: new Date().toISOString() });
    }
};

/* ---------------- Payment UI helpers ---------------- */
const Payments = (() => {
    const CHANNEL = { card: "Card", transfer: "Bank Transfer", virtual: "Virtual Account" };
    const all = () => DB.all("payments");
    const forStudent = (s) => all().filter((p) => p.studentId === s.id || p.email === s.email || p.applicationId === s.appId);

    function receiptHTML(p) {
        const prog = Programmes.get(p.programmeId);
        const inst = Site.settings?.institution || {};
        const set = { name: inst.name, address: inst.address, phone: (inst.phones || []).join(", "), website: inst.website };
        const env = Site.settings?.payments?.environment;
        return `<div class="receipt">
            <div class="receipt-head"><div class="flex">${UI.logoFull("receipt-logo")}<div><h3>${UI.esc(set.name || TSCE_FLYER.name)}</h3><p>${UI.esc(set.address || TSCE_FLYER.address)}</p><p>${UI.esc(set.phone || "")} · ${UI.esc(set.website || "")}</p></div></div>
            <div style="text-align:right"><h3>PAYMENT RECEIPT</h3><p>${UI.dateTime(p.verifiedAt || p.createdAt)}</p></div></div>
            <table>
                <tr><td>Receipt / Transaction Ref.</td><td class="mono">${UI.esc(p.ref)}</td></tr>
                <tr><td>Received from</td><td>${UI.esc(p.name)}</td></tr>
                <tr><td>Email</td><td>${UI.esc(p.email || "—")}</td></tr>
                ${p.applicationId ? `<tr><td>Application No.</td><td class="mono">${UI.esc(p.applicationId)}</td></tr>` : ""}
                ${p.studentId ? `<tr><td>Student ID</td><td class="mono">${UI.esc(p.studentId)}</td></tr>` : ""}
                <tr><td>Description</td><td>${UI.esc(p.description || (prog ? prog.name : "Payment"))}</td></tr>
                ${p.fee && p.fee !== p.amount ? `<tr><td>Programme fee</td><td>${UI.naira(p.fee)}</td></tr><tr><td>Discount applied</td><td style="color:var(--success)">−${UI.naira(p.discount || p.fee - p.amount)}</td></tr>` : ""}
                <tr><td>Payment gateway</td><td>Zainpay${CHANNEL[p.channel] ? " · " + CHANNEL[p.channel] : ""}</td></tr>
                <tr><td>Status</td><td>${p.status}</td></tr>
                <tr class="r-total"><td>Amount paid</td><td>${UI.naira(p.amount)}</td></tr>
            </table>
            ${p.status === "SUCCESS" ? `<span class="stamp">PAID · VERIFIED</span>` : p.status === "REFUNDED" ? `<span class="stamp" style="border-color:var(--info);color:var(--info)">REFUNDED</span>` : ""}
            ${p.kind !== "refund" && Site.settings?.payments?.payerCharge ? `<p class="small muted mt-2 mb-0">The ${UI.naira(Site.settings.payments.payerCharge)} Zainpay transaction charge is paid to the payment provider and is not included above.</p>` : ""}
            <p class="small muted mt-3 mb-0">This is a system-generated receipt from the TSCE Digital Platform${env && env !== "live" ? ` (${env} payment — no real funds were processed)` : ""}.</p>
        </div>`;
    }

    /** ref: a payment object from the API, or (legacy demo pages) a localStorage reference. */
    function showReceipt(ref) {
        const p = typeof ref === "object" ? ref : DB.get("payments", ref);
        if (!p) return UI.toast("Receipt not found", "", "error");
        const m = UI.modal({
            title: "Payment receipt", subtitle: UI.esc(p.ref), size: "lg", body: receiptHTML(p),
            footer: `<button class="btn btn-ghost" data-close>Close</button><button class="btn btn-outline" id="rcDl"><i class="fa-solid fa-download"></i> Download PDF</button><button class="btn btn-primary" id="rcPrint"><i class="fa-solid fa-print"></i> Print</button>`
        });
        const print = () => UI.printHTML(`Receipt ${p.ref}`, receiptHTML(p));
        UI.$("#rcPrint", m.el).onclick = print;
        UI.$("#rcDl", m.el).onclick = () => { UI.toast("Save as PDF", "Choose “Save as PDF” in the print dialog.", "info"); print(); };
    }

    /** Processing modal with animated steps — shared by public checkout and student "Make Payment". */
    function processingModal() {
        const steps = ["Initializing Zainpay transaction", "Authorizing payment", "Verifying transaction", "Updating records"];
        const m = UI.modal({
            size: "sm", bare: true, dismissible: false,
            body: `<div class="processing" aria-live="polite">
                <div class="proc-ring"><svg viewBox="0 0 96 96"><defs><linearGradient id="procGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1846D6"/><stop offset="1" stop-color="#06C8E0"/></linearGradient></defs><circle class="bg" cx="48" cy="48" r="44"/><circle class="fg" cx="48" cy="48" r="44"/></svg><div class="ic"><i class="fa-solid fa-lock"></i></div></div>
                <h3 style="margin-bottom:4px">Processing payment</h3><p class="muted small mb-0">Please don't close this window.</p>
                <div class="proc-steps">${steps.map((s, i) => `<div class="proc-step" data-s="${i}"><i class="fa-solid fa-check"></i>${s}</div>`).join("")}</div>
            </div>`
        });
        return {
            m,
            step(i) {
                UI.$$(".proc-step", m.el).forEach((el, k) => { el.classList.toggle("done", k < i); el.classList.toggle("active", k === i); });
                UI.$(".proc-ring .fg", m.el).style.strokeDashoffset = 276 * (1 - (i + 1) / steps.length);
            },
            success(p, { primary, secondary } = {}) {
                m.setBody(`<div class="processing"><div class="success-mark"><svg viewBox="0 0 52 52"><path d="M14 27l8 8 16-17"/></svg></div>
                    <h3 style="margin-bottom:4px">Payment Successful</h3><p class="muted small">Your payment has been confirmed and verified.</p>
                    <div class="bank-box" style="text-align:left;margin-top:16px">
                        <div class="row"><span class="muted">Amount</span><strong>${UI.naira(p.amount)}</strong></div>
                        <div class="row"><span class="muted">Transaction Reference</span><strong class="mono" style="font-size:.8rem">${UI.esc(p.ref)}</strong></div>
                        <div class="row"><span class="muted">Payment Gateway</span><strong>Zainpay</strong></div>
                        <div class="row"><span class="muted">Status</span>${UI.badge("SUCCESS")}</div>
                    </div>
                    <div class="flex mt-3" style="justify-content:center;flex-wrap:wrap">${secondary || ""}${primary || ""}</div></div>`);
                UI.confetti();
            },
            failure(msg, onRetry) {
                m.setBody(`<div class="processing"><div class="success-mark fail"><svg viewBox="0 0 52 52"><path d="M17 17l18 18M35 17L17 35"/></svg></div>
                    <h3 style="margin-bottom:4px">Payment could not be completed</h3><p class="muted small">${UI.esc(msg || "Please try again.")}</p>
                    <div class="alert warning mt-2" style="text-align:left"><i class="fa-solid fa-circle-info"></i><p>No money was deducted. You can retry with another card or choose Bank Transfer.</p></div>
                    <div class="flex mt-3" style="justify-content:center"><button class="btn btn-ghost" id="pfClose">Close</button><button class="btn btn-primary" id="pfRetry"><i class="fa-solid fa-rotate-right"></i> Try again</button></div></div>`);
                UI.$("#pfClose", m.el).onclick = m.close;
                UI.$("#pfRetry", m.el).onclick = () => { m.close(); onRetry && onRetry(); };
            }
        };
    }

    return { CHANNEL, all, forStudent, receiptHTML, showReceipt, processingModal };
})();

/* ---------------- Public: Payment page (Zainpay checkout) ---------------- */
Pages["payment"] = async function () {
    const wrap = UI.$("#payRoot");
    const number = UI.param("app"), result = UI.param("result"), lastRef = UI.param("ref");
    const user = Auth.current();
    const pset = Site.settings?.payments || {};
    const card = (opts) => `<div class="card">${UI.empty(opts)}</div>`;

    if (result === "unknown") {
        wrap.innerHTML = card({ icon: "fa-circle-question", title: "We couldn't match that payment", text: "If you completed a payment, sign in and open your application — its status updates within a few minutes. Contact TSCE if it doesn't.", action: `<a class="btn btn-primary" href="login.html?role=student">Sign in</a>` });
        return;
    }
    if (!user) {
        wrap.innerHTML = card({ icon: "fa-right-to-bracket", title: "Sign in to pay", text: "Sign in with the email and password you used when applying. You'll come straight back to your invoice.", action: `<a class="btn btn-primary" href="login.html?role=student">Sign in</a> <a class="btn btn-ghost" href="application.html">Start an application</a>` });
        return;
    }
    const appNo = number || user.applicationId;
    if (!appNo) {
        wrap.innerHTML = card({ icon: "fa-file-invoice", title: "No application to pay for", text: "Start an application to generate an invoice and pay securely with Zainpay.", action: `<a class="btn btn-primary" href="application.html">Start application</a>` });
        return;
    }

    wrap.innerHTML = `<div class="card">${UI.skeleton(5)}</div>`;
    let app;
    try { app = await API.get("applications/" + encodeURIComponent(appNo)); }
    catch (e) {
        wrap.innerHTML = card({ icon: "fa-file-circle-xmark", title: e.status === 404 ? "Application not found" : "Couldn't load your invoice", text: e.status === 404 ? `We couldn't find ${UI.esc(appNo)} on the account you're signed in with (${UI.esc(user.email)}).` : UI.esc(e.message), action: `<a class="btn btn-primary" href="application.html">Start application</a>` });
        return;
    }
    if (app.paymentStatus === "Paid") {
        wrap.innerHTML = card({ icon: "fa-circle-check", title: "This application has already been paid", text: `Application ${UI.esc(app.id)} was paid on ${UI.date(app.paidAt)}.`, action: `<a class="btn btn-primary" href="success.html?ref=${encodeURIComponent(app.txRef || "")}">View confirmation</a>` });
        return;
    }
    if (app.status === "Rejected") {
        wrap.innerHTML = card({ icon: "fa-circle-xmark", title: "This application was not successful", text: "It can no longer be paid. Contact the admissions office if you have questions.", action: `<a class="btn btn-primary" href="contact.html">Contact admissions</a>` });
        return;
    }

    const prog = Programmes.get(app.programmeId) || { name: app.programmeName, weeks: "", color: "#1846D6", icon: "fa-layer-group" };
    const env = pset.environment;
    const charge = pset.payerCharge || 0, total = app.amountPayable + charge;
    const methods = [pset.allowCard !== false && ["fa-regular fa-credit-card", "Card", "Visa, Mastercard, Verve"], pset.allowTransfer !== false && ["fa-solid fa-building-columns", "Bank transfer", "Pay from any Nigerian bank app"]].filter(Boolean);
    const alerts = {
        failed: `<div class="alert danger mb-2" role="alert"><i class="fa-solid fa-circle-xmark"></i><p><b>Your last payment didn't go through.</b> No money was taken for it. You can try again below, with another card or by bank transfer.</p></div>`,
        pending: `<div class="alert warning mb-2" id="pendingBox" role="status"><i class="fa-solid fa-hourglass-half"></i><p><b>We're confirming your payment with Zainpay…</b> This usually takes a few seconds, but bank transfers can take a few minutes. <button class="link-btn" id="checkNow">Check now</button></p></div>`
    };

    wrap.innerHTML = `<div class="pay-wrap">
        <div>
            ${alerts[result] || ""}
            <div class="checkout">
                <div class="checkout-head"><div class="zp-logo"><span class="zp-mark"><i class="fa-solid fa-bolt"></i></span><div>Zainpay<small>Secure checkout${env && env !== "live" ? " · " + UI.esc(env) : ""}</small></div></div>
                    <div class="amt"><small>Total to pay</small><strong>${UI.naira(total)}</strong></div></div>
                <div style="padding:22px 24px 6px">
                    <p class="small muted mb-2">You'll be taken to Zainpay's secure payment page${methods.length === 1 && methods[0][1] === "Bank transfer" ? " to pay by bank transfer" : ""}, then brought straight back here.${pset.allowCard !== false ? " TSCE never sees or stores your card details." : ""}</p>
                    <ul class="list">${methods.map(([i, t, d]) => `<li class="list-item"><span class="icon-tile"><i class="${i}"></i></span><div class="grow"><strong>${t}</strong><small>${d}</small></div></li>`).join("")}</ul>
                </div>
                <div style="padding:14px 24px 22px"><button class="btn btn-grad btn-lg btn-block" id="payNow"><i class="fa-solid fa-lock"></i> Pay ${UI.naira(total)} securely</button></div>
                <div class="pay-secure"><i class="fa-solid fa-shield-halved"></i> Secure payment powered by <b>Zainpay</b> · PCI-DSS compliant · 256-bit encryption</div>
            </div>
            ${env && env !== "live" ? `<div class="sandbox-box no-print"><strong><i class="fa-solid fa-flask"></i> ${env === "simulated" ? "Simulated payments" : "Zainpay sandbox"}</strong><p class="small mb-0">${env === "simulated" ? "This server uses the built-in payment simulator — no real money moves. You'll choose the outcome on the next page." : "Sandbox mode — use Zainpay's test cards or test transfer details. No real money moves."}</p></div>` : ""}
        </div>
        <aside class="order-summary">
            <div class="card card-pad">
                <div class="flex between mb-2"><h3 class="mb-0" style="font-size:1.05rem">Order summary</h3>${UI.badge(app.paymentStatus === "Failed" ? "Failed" : "Pending Payment")}</div>
                <div class="flex mb-2" style="align-items:flex-start"><span class="icon-tile" style="background:${prog.color};color:#fff"><i class="fa-solid ${prog.icon}"></i></span><div><strong style="font-family:var(--font-head)">${UI.esc(app.programmeName)}</strong><div class="small muted">${prog.weeks ? prog.weeks + " weeks · " : ""}${UI.esc(app.intake)}</div></div></div>
                <div class="bank-box" style="margin-bottom:14px">
                    <div class="row"><span class="muted">Applicant</span><strong>${UI.esc(app.name)}</strong></div>
                    <div class="row"><span class="muted">Application No.</span><strong class="mono" style="font-size:.84rem">${UI.esc(app.id)}</strong></div>
                    <div class="row"><span class="muted">Schedule</span><strong style="font-size:.84rem;text-align:right">${UI.esc(app.schedule)}</strong></div>
                </div>
                <div class="fee-box">
                    <div class="fee-row"><span>Programme Fee</span><span>${UI.naira(app.fee)}</span></div>
                    ${app.discountAmount ? `<div class="fee-row"><span>${Applications.discountName(app.discountType)} (${app.discountPct}%)</span><span class="neg">−${UI.naira(app.discountAmount)}</span></div>` : ""}
                    <div class="fee-row total"><span>Amount Payable</span><span>${UI.naira(app.amountPayable)}</span></div>
                    ${charge ? `<div class="fee-row"><span>Zainpay transaction charge</span><span>${UI.naira(charge)}</span></div><div class="fee-row total"><span>Total to pay</span><span>${UI.naira(total)}</span></div>` : ""}
                </div>
                ${app.awardRequest?.status === "Pending" ? `<div class="alert mt-2"><i class="fa-solid fa-award"></i><p>Your <b>${Applications.discountName(app.awardRequest.type)}</b> request will be reviewed by admissions. If approved, the difference is refunded to you.</p></div>` : ""}
                <div class="flex mt-2 small muted"><i class="fa-solid fa-circle-check" style="color:var(--success)"></i> Instant confirmation & e-receipt</div>
                <div class="flex mt-1 small muted"><i class="fa-solid fa-circle-check" style="color:var(--success)"></i> Student portal activated after payment</div>
            </div>
        </aside></div>`;

    const payBtn = UI.$("#payNow");
    payBtn.onclick = async () => {
        payBtn.disabled = true; payBtn.innerHTML = `<span class="spinner"></span> Connecting to Zainpay…`;
        try {
            const r = await API.post("payments/initialize", { applicationId: app.id });
            if (r.amount !== app.amountPayable) {
                const go = await UI.confirm({ title: "Amount updated", message: `The early-bird period has ended, so the amount payable is now <b>${UI.naira(r.amount)}</b>${charge ? ` (plus the ${UI.naira(charge)} Zainpay charge)` : ""}.`, confirmText: `Pay ${UI.naira(r.amount + charge)}`, icon: "fa-circle-info" });
                if (!go) { location.reload(); return; }
            }
            location.href = r.checkoutUrl;
        } catch (err) {
            payBtn.disabled = false; payBtn.innerHTML = `<i class="fa-solid fa-lock"></i> Pay ${UI.naira(total)} securely`;
            UI.toast(err.code === "programme_full" ? "Programme full" : "Payment not started", err.message, "error", 8000);
            if (err.code === "already_paid") location.reload();
        }
    };

    // Back from checkout but not confirmed yet: ask again a few times, then leave it to the cron job.
    if (result === "pending" && lastRef) {
        let tries = 0, busy = false;
        const check = async (manual) => {
            if (busy) return; busy = true;
            try {
                const p = await API.post(`payments/${encodeURIComponent(lastRef)}/check`);
                if (p.status === "SUCCESS") { location.href = `success.html?ref=${encodeURIComponent(p.ref)}`; return; }
                if (p.status === "FAILED") { location.href = `payment.html?app=${encodeURIComponent(app.id)}&result=failed`; return; }
                if (manual) UI.toast("Still processing", "Zainpay hasn't confirmed this payment yet. We'll keep checking.", "info");
            } catch (e) { if (manual) UI.toast("Couldn't check", e.message, "warning"); }
            finally { busy = false; }
        };
        UI.$("#checkNow").onclick = () => check(true);
        const timer = setInterval(() => { if (++tries > 10) { clearInterval(timer); UI.$("#pendingBox p").insertAdjacentHTML("beforeend", " <br><span class='small'>If you paid, you don't need to pay again — it will be confirmed automatically and you'll get a notification.</span>"); return; } check(false); }, 5000);
        check(false);
    }
};

/* ---------------- Public: Success page ---------------- */
Pages["success"] = async function () {
    const box = UI.$("#successRoot");
    const ref = UI.param("ref");
    const empty = (opts) => box.innerHTML = `<div class="card">${UI.empty(opts)}</div>`;
    if (!ref) return empty({ icon: "fa-hourglass-half", title: "No completed payment to show", text: "Once your payment is confirmed, your confirmation appears here.", action: `<a class="btn btn-primary" href="application.html">Start application</a>` });
    if (!Auth.current()) return empty({ icon: "fa-right-to-bracket", title: "Sign in to view your confirmation", text: "For your privacy, payment details are only shown to the account that paid.", action: `<a class="btn btn-primary" href="login.html?role=student">Sign in</a>` });

    box.innerHTML = `<div class="card">${UI.skeleton(6)}</div>`;
    let pay, app;
    try {
        pay = await API.get(`payments/${encodeURIComponent(ref)}`);
        if (pay.status !== "SUCCESS") { location.replace(`payment.html?app=${encodeURIComponent(pay.applicationId || "")}&ref=${encodeURIComponent(ref)}&result=${pay.status === "FAILED" ? "failed" : "pending"}`); return; }
        app = await API.get("applications/" + encodeURIComponent(pay.applicationId));
    } catch (e) {
        return empty({ icon: "fa-receipt", title: "We couldn't load this confirmation", text: UI.esc(e.message), action: `<a class="btn btn-primary" href="../index.html">Back to home</a>` });
    }
    const start = Site.day(app.cohortStart);
    box.innerHTML = `<div class="success-card">
        <div class="success-top"><div class="success-mark"><svg viewBox="0 0 52 52"><path d="M14 27l8 8 16-17"/></svg></div>
            <span class="badge badge-success mb-2">Payment verified</span>
            <h1>APPLICATION SUBMITTED SUCCESSFULLY</h1>
            <p class="muted" style="max-width:560px;margin:0 auto 12px">Thank you, ${UI.esc(app.firstName)}. Your application and payment have been received. Your student portal account is now active${pay.studentId ? ` — your student number is <b>${UI.esc(pay.studentId)}</b>` : ""}.</p>
            <div class="app-no"><div><small>Application Number</small><br><strong>${UI.esc(app.id)}</strong></div><button class="icon-btn" id="copyApp" aria-label="Copy application number"><i class="fa-regular fa-copy"></i></button></div>
        </div>
        <div class="success-details">
            <div><small>Applicant</small><strong>${UI.esc(app.name)}</strong></div>
            <div><small>Programme</small><strong>${UI.esc(app.programmeName)}</strong></div>
            <div><small>Cohort</small><strong>${UI.esc(app.intake)}</strong></div>
            <div><small>Payment status</small>${UI.badge("Paid")}</div>
            <div><small>Application status</small>${UI.badge(app.status === "Pending" ? "Submitted" : app.status)}</div>
            <div><small>Transaction reference</small><strong class="mono" style="font-size:.82rem">${UI.esc(pay.ref)}</strong></div>
            <div><small>Amount paid</small><strong>${UI.naira(pay.amount)}</strong></div>
            <div><small>Discount</small><strong>${app.discountAmount ? `${Applications.discountName(app.discountType)} (−${UI.naira(app.discountAmount)})` : "None"}</strong></div>
            <div><small>Classes begin</small><strong>${UI.dateLong(start)}</strong></div>
        </div>
        <div class="success-actions no-print">
            <button class="btn btn-outline" id="dlReceipt"><i class="fa-solid fa-download"></i> Download Receipt</button>
            <button class="btn btn-outline" id="printApp"><i class="fa-solid fa-print"></i> Print Application</button>
            <a class="btn btn-primary" href="student/dashboard.html"><i class="fa-solid fa-user-graduate"></i> Go to Student Portal</a>
        </div></div>
        <div class="next-steps no-print">
            <div class="card card-pad"><span class="icon-tile"><i class="fa-solid fa-receipt"></i></span><h4 class="mt-2">Keep your receipt</h4><p class="small muted mb-0">Download it now. It's also available any time in your student portal.</p></div>
            <div class="card card-pad"><span class="icon-tile cyan"><i class="fa-solid fa-magnifying-glass"></i></span><h4 class="mt-2">Admission review</h4><p class="small muted mb-0">The admissions office will review your application and notify you in your portal.</p></div>
            <div class="card card-pad"><span class="icon-tile gold"><i class="fa-solid fa-calendar-check"></i></span><h4 class="mt-2">Get ready</h4><p class="small muted mb-0">Classes start on ${UI.date(start)}. Watch your portal for orientation details.</p></div>
        </div>`;
    if (UI.param("fresh") !== "0") UI.confetti();
    UI.$("#copyApp").onclick = () => UI.copy(app.id);
    UI.$("#dlReceipt").onclick = () => Payments.showReceipt(pay);
    UI.$("#printApp").onclick = () => UI.printHTML(`Application ${app.id}`, Applications.printHTML(app));
};

/* ---------------- Staff: Payment management ---------------- */
Pages["staff-payments"] = function (view) {
    let statusFilter = UI.param("status") || "";
    view.innerHTML = `
        <div class="view-head"><div><h2>Payments & Transactions</h2><p>All Zainpay transactions — verify pending transfers, issue refunds and print receipts.</p></div>
            <div class="actions"><button class="btn btn-primary" id="expPay"><i class="fa-solid fa-file-csv"></i> Export CSV</button></div></div>
        <div class="kpis" id="payKpis"></div>
        <div class="dash-grid cols-12" style="margin-bottom:20px">
            <div class="panel span-8"><div class="panel-head"><div><h3><i class="fa-solid fa-chart-column"></i>Daily collections</h3><p>Successful Zainpay payments — last 21 days</p></div></div><div class="panel-body"><div class="chart-box sm"><canvas id="payDaily"></canvas></div></div></div>
            <div class="panel span-4"><div class="panel-head"><h3><i class="fa-solid fa-wallet"></i>By channel</h3></div><div class="panel-body"><div class="chart-box sm"><canvas id="payChannel"></canvas></div></div></div>
        </div>
        <div class="panel">
            <div class="table-tools"><div class="input-icon"><i class="fa-solid fa-magnifying-glass"></i><input class="input" id="tSearch" placeholder="Search name, reference, application…" aria-label="Search transactions"></div>
                <select class="select" id="tStatus" aria-label="Status"><option value="">All statuses</option><option>SUCCESS</option><option>PENDING</option><option>FAILED</option><option>REFUNDED</option></select>
                <select class="select" id="tChannel" aria-label="Channel"><option value="">All channels</option><option value="card">Card</option><option value="transfer">Bank Transfer</option><option value="virtual">Virtual Account</option></select>
                <select class="select" id="tProg" aria-label="Programme"><option value="">All programmes</option>${Programmes.all().map((p) => `<option value="${p.id}">${UI.esc(p.name)}</option>`).join("")}</select></div>
            <div id="payTable"></div></div>`;
    UI.$("#tStatus").value = statusFilter;

    function kpis() {
        const ps = Payments.all(); const base = DB.settings().baselines || {};
        const sum = (s) => ps.filter((p) => p.status === s).reduce((a, p) => a + p.amount, 0);
        const cnt = (s) => ps.filter((p) => p.status === s).length;
        UI.$("#payKpis").innerHTML = [
            ["Total revenue", UI.naira(sum("SUCCESS") + (base.revenue || 0)), "fa-naira-sign", "grad", "All-time, incl. archived cohorts"],
            ["Successful", cnt("SUCCESS"), "fa-circle-check", "green", UI.naira(sum("SUCCESS"), { compact: true }) + " this intake"],
            ["Pending", cnt("PENDING"), "fa-hourglass-half", "gold", UI.naira(sum("PENDING")) + " awaiting"],
            ["Failed", cnt("FAILED"), "fa-circle-xmark", "red", "Needs follow-up"],
            ["Refunded", cnt("REFUNDED"), "fa-rotate-left", "cyan", UI.naira(sum("REFUNDED")) + " returned"]
        ].map(([l, v, i, c, n], k) => `<div class="kpi ${k === 0 ? "" : ""}" data-kfilter="${["", "SUCCESS", "PENDING", "FAILED", "REFUNDED"][k]}" style="cursor:pointer"><div class="kpi-top"><p class="label">${l}</p><span class="icon-tile ${c}"><i class="fa-solid ${i}"></i></span></div><div class="value">${v}</div><div class="small muted mt-1">${n}</div></div>`).join("");
        UI.$$("[data-kfilter]").forEach((k) => k.onclick = () => { UI.$("#tStatus").value = k.dataset.kfilter; refresh(); });
    }
    const table = UI.dataTable("#payTable", {
        pageSize: 10, onRowClick: (id) => detail(id),
        columns: [
            { key: "ref", label: "Transaction", render: (p) => `<span class="ref">${UI.esc(p.ref)}</span>` },
            { key: "name", label: "Student", render: (p) => `<div class="person">${UI.avatar(p.name, "sm")}<div><strong>${UI.esc(p.name)}</strong><small>${UI.esc(p.studentId || p.applicationId || "")}</small></div></div>` },
            { key: "programmeId", label: "Programme", render: (p) => `<span class="small">${UI.esc(Programmes.name(p.programmeId))}</span>` },
            { key: "amount", label: "Amount", cls: "num", render: (p) => `<b>${UI.naira(p.amount)}</b>` },
            { key: "gateway", label: "Gateway", render: (p) => `<span class="small"><i class="fa-solid fa-bolt" style="color:var(--secondary)"></i> Zainpay · ${Payments.CHANNEL[p.channel] || "Card"}</span>` },
            { key: "status", label: "Status", render: (p) => UI.badge(p.status) },
            { key: "createdAt", label: "Date", render: (p) => `<span class="small">${UI.dateTime(p.createdAt)}</span>` }
        ],
        mobile: (p) => `<div class="m-row"><strong>${UI.esc(p.name)}</strong>${UI.badge(p.status)}</div><div class="m-row"><span class="ref">${UI.esc(p.ref)}</span><b>${UI.naira(p.amount)}</b></div><div class="m-row"><span>${UI.esc(Programmes.name(p.programmeId))}</span><span>${UI.date(p.createdAt)}</span></div>`
    });
    function refresh() {
        const q = UI.$("#tSearch").value.toLowerCase(), st = UI.$("#tStatus").value, ch = UI.$("#tChannel").value, pr = UI.$("#tProg").value;
        table.update(Payments.all().filter((p) => (!st || p.status === st) && (!ch || p.channel === ch) && (!pr || p.programmeId === pr) && [p.name, p.ref, p.applicationId, p.studentId, p.email].join(" ").toLowerCase().includes(q)).sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt)), { resetPage: false });
        kpis();
    }
    function charts() {
        if (!window.Chart) return;
        const ps = Payments.all().filter((p) => p.status === "SUCCESS");
        const days = Array.from({ length: 21 }, (_, i) => { const d = new Date(); d.setDate(d.getDate() - 20 + i); return d; });
        const key = (d) => new Date(d).toISOString().slice(0, 10);
        const byDay = days.map((d) => ps.filter((p) => key(p.createdAt) === key(d)).reduce((a, p) => a + p.amount, 0) + (Dashboard.seedNoise(key(d)) * 42500));
        Dashboard.chart("payDaily", { type: "bar", data: { labels: days.map((d) => UI.date(d, { day: "numeric", month: "short" })), datasets: [{ label: "Collections", data: byDay, backgroundColor: "#1846D6", borderRadius: 6, maxBarThickness: 22 }] }, options: { plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => UI.naira(c.raw) } } }, scales: { y: { ticks: { callback: (v) => UI.naira(v, { compact: true }) } } } } });
        const chs = ["card", "transfer", "virtual"];
        Dashboard.chart("payChannel", { type: "doughnut", data: { labels: chs.map((c) => Payments.CHANNEL[c]), datasets: [{ data: chs.map((c) => ps.filter((p) => p.channel === c).length), backgroundColor: ["#1846D6", "#06C8E0", "#F5B400"], borderWidth: 0 }] }, options: { cutout: "68%", plugins: { legend: { position: "bottom" } } } });
    }
    function detail(ref) {
        const p = DB.get("payments", ref);
        const actions = [];
        if (p.status === "PENDING") actions.push(`<button class="btn btn-success" id="pVerify"><i class="fa-solid fa-shield-halved"></i> Verify with Zainpay</button>`);
        if (p.status === "SUCCESS") actions.push(`<button class="btn btn-soft-danger" id="pRefund"><i class="fa-solid fa-rotate-left"></i> Refund</button>`);
        if (p.status === "FAILED") actions.push(`<button class="btn btn-outline" id="pRemind"><i class="fa-regular fa-bell"></i> Send payment reminder</button>`);
        if (p.status === "SUCCESS" || p.status === "REFUNDED") actions.push(`<button class="btn btn-primary" id="pReceipt"><i class="fa-solid fa-receipt"></i> Receipt</button>`);
        const d = UI.drawer({
            title: `Transaction ${UI.badge(p.status)}`, subtitle: `<span class="mono">${UI.esc(p.ref)}</span>`,
            body: `<div class="dr-section"><h4>Payment</h4><div class="kv">
                    <div><small>Amount</small><strong style="font-size:1.3rem;font-family:var(--font-head)">${UI.naira(p.amount)}</strong></div>
                    <div><small>Gateway</small><strong>Zainpay · ${Payments.CHANNEL[p.channel] || "Card"}</strong></div>
                    <div><small>Programme fee</small><strong>${UI.naira(p.fee || p.amount)}</strong></div>
                    <div><small>Discount</small><strong>${p.discount ? "−" + UI.naira(p.discount) : "—"}</strong></div>
                    <div class="full"><small>Description</small><strong>${UI.esc(p.description || "")}</strong></div>
                    ${p.failureReason ? `<div class="full"><small>Failure reason</small><strong style="color:var(--danger)">${UI.esc(p.failureReason)}</strong></div>` : ""}
                </div></div>
                <div class="dr-section"><h4>Customer</h4><div class="kv"><div><small>Name</small><strong>${UI.esc(p.name)}</strong></div><div><small>Email</small><strong>${UI.esc(p.email || "—")}</strong></div>
                    <div><small>Application</small><strong class="mono">${UI.esc(p.applicationId || "—")}</strong></div><div><small>Student ID</small><strong class="mono">${UI.esc(p.studentId || "—")}</strong></div></div></div>
                <div class="dr-section"><h4>Gateway timeline</h4><ul class="history">
                    <li class="ok"><strong>Transaction initialised</strong><small>${UI.dateTime(p.createdAt)}</small></li>
                    ${p.status === "PENDING" ? `<li><strong>Awaiting confirmation from bank</strong><small>Transfer not yet settled</small></li>` : ""}
                    ${p.status === "FAILED" ? `<li><strong>Declined by issuer</strong><small>${UI.dateTime(p.verifiedAt || p.createdAt)}</small></li>` : ""}
                    ${["SUCCESS", "REFUNDED"].includes(p.status) ? `<li class="ok"><strong>Payment approved & verified</strong><small>${UI.dateTime(p.verifiedAt || p.createdAt)}</small></li>` : ""}
                    ${p.status === "REFUNDED" ? `<li><strong>Refund processed</strong><small>${UI.dateTime(p.refundedAt)}</small></li>` : ""}
                </ul></div>`,
            footer: actions.join("") || `<button class="btn btn-ghost" data-close>Close</button>`
        });
        UI.$("#pVerify", d.el)?.addEventListener("click", async (e) => {
            e.target.disabled = true; e.target.innerHTML = `<span class="spinner"></span> Verifying…`;
            const upd = await PaymentService.verify(ref);
            if (upd.applicationId && upd.status === "SUCCESS") Applications.markPaid(upd.applicationId, upd, { silent: true });
            d.close(); UI.toast("Payment verified", `${p.name} — ${UI.naira(p.amount)} confirmed by Zainpay.`, "success"); refresh(); charts();
        });
        UI.$("#pRefund", d.el)?.addEventListener("click", async () => {
            if (!(await UI.confirm({ title: "Refund this payment?", message: `${UI.naira(p.amount)} will be returned to ${UI.esc(p.name)} via Zainpay.`, confirmText: "Issue refund", tone: "danger", icon: "fa-rotate-left" }))) return;
            DB.update("payments", ref, { status: "REFUNDED", refundedAt: new Date().toISOString() });
            if (p.email) Notifications.push(p.email, "Refund processed", `A refund of ${UI.naira(p.amount)} (${p.ref}) has been processed.`, "payment");
            d.close(); UI.toast("Refund issued", `${UI.naira(p.amount)} refunded (simulated).`, "success"); refresh(); charts();
        });
        UI.$("#pRemind", d.el)?.addEventListener("click", () => { if (p.email) Notifications.push(p.email, "Complete your payment", `Your payment for ${Programmes.name(p.programmeId)} did not go through. Please try again.`, "payment"); d.close(); UI.toast("Reminder sent", `Email + SMS reminder sent to ${p.name} (simulated).`, "success"); });
        UI.$("#pReceipt", d.el)?.addEventListener("click", () => Payments.showReceipt(ref));
    }
    ["#tSearch", "#tStatus", "#tChannel", "#tProg"].forEach((s) => UI.$(s).addEventListener(s === "#tSearch" ? "input" : "change", UI.debounce(refresh, 120)));
    UI.$("#expPay").onclick = () => UI.downloadCSV("tsce-transactions.csv", Payments.all().map((p) => ({ Reference: p.ref, Student: p.name, Email: p.email, Application: p.applicationId, Programme: Programmes.name(p.programmeId), Amount: p.amount, Gateway: "Zainpay", Channel: Payments.CHANNEL[p.channel], Status: p.status, Date: UI.dateTime(p.createdAt) })));
    refresh(); charts();
    const open = UI.param("ref"); if (open && DB.get("payments", open)) detail(open);
};

/* ---------------- Student: Payments ---------------- */
Pages["student-payments"] = function (view, ctx) {
    const s = ctx.student;
    const pays = () => Payments.forStudent(s).sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
    const app = DB.get("applications", s.appId);
    const prog = Programmes.get(s.programmeId);

    function render() {
        const list = pays();
        const paid = list.filter((p) => p.status === "SUCCESS").reduce((a, p) => a + p.amount, 0);
        const tuitionPaid = app && app.paymentStatus === "Paid";
        view.innerHTML = `
        <div class="view-head"><div><h2>Payments</h2><p>Invoices, payment history and receipts — processed securely by Zainpay.</p></div>
            <div class="actions"><button class="btn btn-primary" id="makePay"><i class="fa-solid fa-credit-card"></i> Make Payment</button></div></div>
        <div class="kpis">
            <div class="kpi"><div class="kpi-top"><p class="label">Programme fee</p><span class="icon-tile"><i class="fa-solid fa-file-invoice"></i></span></div><div class="value">${UI.naira(prog.fee)}</div></div>
            <div class="kpi"><div class="kpi-top"><p class="label">Discount</p><span class="icon-tile gold"><i class="fa-solid fa-tags"></i></span></div><div class="value">${UI.naira(app?.discountAmount || 0)}</div><div class="small muted mt-1">${Applications.discountName(app?.discountType)}</div></div>
            <div class="kpi"><div class="kpi-top"><p class="label">Total paid</p><span class="icon-tile green"><i class="fa-solid fa-circle-check"></i></span></div><div class="value">${UI.naira(paid)}</div></div>
            <div class="kpi"><div class="kpi-top"><p class="label">Outstanding balance</p><span class="icon-tile cyan"><i class="fa-solid fa-scale-balanced"></i></span></div><div class="value">${UI.naira(tuitionPaid ? 0 : app?.amountPayable || 0)}</div><div class="mt-1">${UI.badge(tuitionPaid ? "Paid" : "Unpaid")}</div></div>
        </div>
        <div class="dash-grid cols-12">
            <div class="panel span-5"><div class="panel-head"><h3><i class="fa-solid fa-file-invoice-dollar"></i>Invoices</h3></div>
                <ul class="list">
                    <li class="list-item"><span class="icon-tile"><i class="fa-solid fa-graduation-cap"></i></span><div class="grow"><strong>Tuition — ${UI.esc(prog.name)}</strong><small>INV-${UI.esc((s.appId || "").split("/").pop())} · ${UI.esc(s.cohort)}</small></div><div style="text-align:right"><b>${UI.naira(app?.amountPayable || prog.fee)}</b><div>${UI.badge(tuitionPaid ? "Paid" : "Unpaid")}</div></div></li>
                    ${list.filter((p) => !p.applicationId && p.status === "SUCCESS").map((p) => `<li class="list-item"><span class="icon-tile gold"><i class="fa-solid fa-receipt"></i></span><div class="grow"><strong>${UI.esc(p.description)}</strong><small>${UI.date(p.createdAt)}</small></div><div style="text-align:right"><b>${UI.naira(p.amount)}</b><div>${UI.badge("Paid")}</div></div></li>`).join("")}
                </ul>
                ${!tuitionPaid && app ? `<div class="panel-body"><a class="btn btn-grad btn-block" href="../payment.html?app=${encodeURIComponent(app.id)}">Pay tuition now</a></div>` : ""}
            </div>
            <div class="panel span-7"><div class="panel-head"><h3><i class="fa-solid fa-clock-rotate-left"></i>Payment history</h3></div><div id="stuPayTable"></div></div>
        </div>`;
        UI.dataTable("#stuPayTable", {
            rows: list, pageSize: 6, onRowClick: (id) => Payments.showReceipt(id),
            empty: { icon: "fa-receipt", title: "No payments yet", text: "Your Zainpay transactions will appear here." },
            columns: [
                { key: "ref", label: "Reference", render: (p) => `<span class="ref">${UI.esc(p.ref)}</span><div class="small muted">${UI.esc(p.description || "")}</div>` },
                { key: "amount", label: "Amount", cls: "num", render: (p) => `<b>${UI.naira(p.amount)}</b>` },
                { key: "status", label: "Status", render: (p) => UI.badge(p.status) },
                { key: "createdAt", label: "Date", render: (p) => UI.date(p.createdAt) },
                { key: "", label: "", sortable: false, render: (p) => p.status === "SUCCESS" || p.status === "REFUNDED" ? `<button class="btn btn-xs btn-soft">Receipt</button>` : "" }
            ]
        });
        UI.$("#makePay").onclick = makePayment;
    }

    function makePayment() {
        const items = [
            { id: "tuition", label: `Tuition balance — ${prog.name}`, amount: app && app.paymentStatus !== "Paid" ? app.amountPayable : 0 },
            { id: "cert", label: "Certificate reprint (demo item)", amount: 5000 },
            { id: "resit", label: "Assessment resit fee (demo item)", amount: 7500 },
            { id: "transcript", label: "Official transcript (demo item)", amount: 3000 }
        ].filter((x) => x.amount > 0);
        const m = UI.modal({
            title: "Make a payment", subtitle: "Secure payment powered by Zainpay", size: "sm",
            body: `<div class="field mb-2"><label for="mpItem">What are you paying for?</label><select id="mpItem" class="select">${items.map((x) => `<option value="${x.id}">${UI.esc(x.label)} — ${UI.naira(x.amount)}</option>`).join("")}</select></div>
                <div class="field mb-2"><label>Payment method</label><div class="option-grid" style="grid-template-columns:1fr 1fr 1fr">${["card", "transfer", "virtual"].map((c, i) => `<label class="option-card" style="padding:10px;flex-direction:column;align-items:center;text-align:center;gap:4px"><input type="radio" name="mpCh" value="${c}" ${i === 0 ? "checked" : ""}><i class="fa-solid ${["fa-credit-card", "fa-building-columns", "fa-wallet"][i]}" style="color:var(--primary)"></i><small style="font-weight:700;color:var(--text-2)">${Payments.CHANNEL[c]}</small></label>`).join("")}</div></div>
                <div class="fee-box"><div class="fee-row total"><span>Total</span><span id="mpTotal">${UI.naira(items[0].amount)}</span></div></div>`,
            footer: `<button class="btn btn-ghost" data-close>Cancel</button><button class="btn btn-grad" id="mpPay"><i class="fa-solid fa-lock"></i> Pay now</button>`
        });
        const sel = UI.$("#mpItem", m.el);
        sel.onchange = () => UI.$("#mpTotal", m.el).textContent = UI.naira(items.find((x) => x.id === sel.value).amount);
        UI.$("#mpPay", m.el).onclick = async () => {
            const item = items.find((x) => x.id === sel.value);
            if (item.id === "tuition") { location.href = `../payment.html?app=${encodeURIComponent(app.id)}`; return; }
            const ch = UI.$('input[name="mpCh"]:checked', m.el).value;
            m.close();
            const proc = Payments.processingModal();
            const p = await PaymentService.checkout({ amount: item.amount, email: s.email, name: `${s.firstName} ${s.lastName}`, description: item.label.replace(" (demo item)", ""), channel: ch, studentId: s.id, programmeId: s.programmeId }, (i) => proc.step(i));
            if (p.status !== "SUCCESS") return proc.failure("Payment could not be completed. Please try again.", makePayment);
            Notifications.push(s.email, "Payment successful", `Your payment of ${UI.naira(p.amount)} was successful. Ref: ${p.ref}`, "payment");
            Notifications.push("staff", "Payment received", `${s.firstName} ${s.lastName} paid ${UI.naira(p.amount)} — ${p.description}.`, "payment");
            proc.success(p, { primary: `<button class="btn btn-primary" id="mpDone">Done</button>`, secondary: `<button class="btn btn-outline" id="mpRc">Receipt</button>` });
            UI.$("#mpDone", proc.m.el).onclick = () => { proc.m.close(); render(); Dashboard.refreshBell(); };
            UI.$("#mpRc", proc.m.el).onclick = () => Payments.showReceipt(p.ref);
        };
    }
    render();
};
