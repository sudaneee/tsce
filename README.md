# TSCE Digital Platform

> **Backend in progress.** The approved frontend now lives in `frontend/`. A Django + SQLite backend in `backend/` is replacing the localStorage demo layer one phase at a time. See [PLAN.md](PLAN.md). Until a page is wired to the API, it still uses the demo data described below.

## Development setup (Django)

Requires Python 3.12+. From the repo root:

```bash
python -m venv backend/.venv
backend/.venv/Scripts/pip install -r backend/requirements.txt   # Linux/macOS: backend/.venv/bin/pip
cd backend
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py createsuperuser                  # admin role, Django admin access
.venv/Scripts/python manage.py runserver
# Site:  http://localhost:8000      API: http://localhost:8000/api/health      Admin: http://localhost:8000/admin/
.venv/Scripts/python manage.py test apps                        # run the test suite
```

- In development, Django serves `frontend/` too, so there's one server and one origin. In production, nginx serves `frontend/` and proxies `/api/` and `/admin/` to gunicorn.
- Configuration comes from `backend/.env`. Copy `backend/.env.example` to create it. Dev works without a `.env`; production requires one.
- The frontend talks to the backend only through `frontend/js/api.js`, which handles the CSRF token, JSON or multipart bodies, and the error shape `{ error, code, fields }`.
- **Seed the school data** (settings, current cohort, 11 programmes): `python manage.py seed_school`

### Payments (Zainpay)

- `PAYMENT_GATEWAY=simulator` (the default in development) replaces Zainpay's hosted checkout with a local page where you choose *Pay*, *Decline* or *Cancel*. No keys are needed and no money moves. Production refuses to start with the simulator unless `ALLOW_PAYMENT_SIMULATOR=true` (demo servers only).
- `PAYMENT_GATEWAY=zainpay` with `ZAINPAY_ENVIRONMENT=sandbox|live` and the keys in `backend/.env` (see `.env.example`). Register `https://<domain>/api/payments/zainpay/webhook` as the webhook URL in the Zainpay dashboard.
- Run `python manage.py reconcile_payments` from cron every 5 minutes. It confirms payments whose callback and webhook were both missed.
- The flow and the hard-won details of Zainpay's API (two success shapes, ambiguous "Txn not found") are documented at the top of `backend/apps/payments/gateways.py`.

### Browser tests

End-to-end tests drive a real browser (headless Edge by default) against a dev server on a throwaway database in `.e2e/work/`:

```bash
python -m venv .e2e/venv && .e2e/venv/Scripts/pip install -r e2e/requirements.txt   # once
bash e2e/run.sh            # all suites
bash e2e/run.sh payments   # one suite: e2e/setup_payments.py + e2e/test_payments.py
```

---

## The original demo

Frontend MVP for **Trust Skills Center of Excellence (TSCE), Zaria**. It includes a public website, an online application wizard, a simulated Zainpay checkout, a student portal and a staff/admin portal. Everything is built with HTML, CSS and vanilla JavaScript. A simulated backend runs in the browser on `localStorage`.

> **Demo mode.** All people, scores, transactions and dashboard figures are demo data. The flyer data (programme names, fees, durations, dates, discounts, phone numbers, address and website) is kept as published. It lives in `TSCE_FLYER` and `PROGRAMME_CATALOGUE` in `js/data.js`.

## Run locally

The app has no build step. It's best to serve it over HTTP so every page shares the same `localStorage`:

```bash
cd tsce-platform
python -m http.server 8080        # or: npx serve .  /  VS Code "Live Server"
# open http://localhost:8080
```

You can also open `index.html` directly in Chrome or Edge. Some browsers keep separate storage per file:// page, though, so use a local server for demos.

An internet connection is needed for the CDN assets: Google Fonts, Font Awesome and Chart.js.

## Demo credentials

| Role | Email | Password |
|---|---|---|
| Student | amina.yusuf@example.com | student123 |
| Student | muhammad.ibrahim@example.com | student123 |
| Admin (staff portal) | admin@tsce.edu.ng | admin123 |
| Staff (admissions officer, no Settings or Staff pages) | admissions@tsce.edu.ng | staff123 |
| Applicant (applied, not yet paid; login opens the payment page) | mustapha.yakubu@example.com | applicant123 |

The login page has one-click **Enter Demo** buttons. Every public page has a **DEMO MODE** chip and an **Explore Platform** button that opens a guided tour.

To restore the original data, go to **Staff → Settings → Demo data → Reset**.

## Suggested management demo (about 5 minutes)

1. **Home.** Show the hero, programmes, scholarships, timeline and countdown.
2. **Programmes → Full-Stack.** Show the curriculum, outcomes and live seat count, then click *Apply*.
3. **Application.** Click *Autofill demo applicant*, then *Continue* three times. The review step shows ₦50,000 − ₦7,500 early bird = **₦42,500**.
4. **Payment.** On the Zainpay checkout, click *Pay ₦42,500*. You'll see processing, then success and a receipt.
5. **Success page.** It shows the application number and the Download Receipt, Print and **Go to Student Portal** buttons.
6. **Student (Amina).** Dashboard, Attendance, Results (chart), Certificate and Payments (*Make Payment*).
7. **Staff (admin).**
   - Dashboard analytics.
   - Applications: approve and enrol a paid applicant.
   - Scholarships: review an award.
   - Payments: verify a pending transfer or issue a refund.
   - Reports: export a CSV or print.
   - Press **Ctrl K** for global search.

The early-bird discount uses the real date: it applies automatically before 1 October 2026. To demo after that date, change *Early-bird deadline* in **Staff → Settings → Admissions**.

## File structure

```
tsce-platform/
├── index.html                 Home page (15 sections)
├── pages/
│   ├── about, programmes, admissions, contact, news, verify .html
│   ├── login.html             Role-based sign-in + demo panel
│   ├── application.html       4-step wizard + discount engine
│   ├── payment.html           Zainpay checkout (simulated)
│   ├── success.html           Confirmation, receipt, portal hand-off
│   ├── student/               dashboard, profile, programme, learning, attendance,
│   │                          results, payments, certificates, announcements, support, settings
│   └── staff/                 dashboard, applications, students, programmes, payments,
│                              attendance, assessments, scholarships, certificates,
│                              reports, announcements, settings, staff
├── assets/logo/              Official TSCE logo: tsce-logo-full.png (full lockup — certificates,
│                             receipts, prints), tsce-emblem.png (header/sidebar mark), favicon.png
├── css/  main.css (design system + public) · dashboard.css (portals) · responsive.css
└── js/
    ├── data.js           Flyer data, programme catalogue, deterministic demo seed
    ├── storage.js        DB wrapper over localStorage (tsce_* keys)
    ├── ui.js             Toasts, modals, drawers, tables, validation, CSV/print
    ├── auth.js           Simulated role-based auth + login page
    ├── programmes.js     Catalogue, detail modal, staff programme management
    ├── payments.js       ZainpaySimulator, PaymentService, checkout, receipts
    ├── applications.js   Discount engine, application wizard, staff applications, scholarships
    ├── students.js       Student portal pages, attendance, assessments, certificates
    ├── notifications.js  Notifications, announcements, news
    ├── dashboard.js      Portal shell, global search, dashboards, staff, settings
    ├── reports.js        Six management reports
    └── app.js            Public header/footer, demo tour, page router
```

The `localStorage` keys are `tsce_users`, `tsce_students`, `tsce_applications`, `tsce_payments`, `tsce_programmes`, `tsce_attendance`, `tsce_results`, `tsce_scholarships`, `tsce_notifications`, `tsce_announcements`, `tsce_staff` and `tsce_settings`.

## Simulated Zainpay flow

```
Application → Invoice created → Zainpay checkout → Processing → Payment successful
→ Transaction verified → Application paid → Student account activated
```

- **`ZainpaySimulator`** (in `js/payments.js`) behaves like a gateway API:
  - `generateTransactionReference()` returns a reference like `TSCE-ZP-20261001-001245`.
  - `initializePayment()` returns `{ code: "00", data: { txnRef, checkoutUrl } }`.
  - `processPayment()` takes 1.5–2.5 seconds.
  - `verifyPayment()` returns the transaction status.
- **Sandbox rules:**
  - A card number ending in `0002` is declined.
  - The payment page has an *outcome* selector for simulating a failure.
- **`PaymentService.checkout()`** runs initialise → process → verify, then stores the payment record. After that, `Applications.markPaid()` updates the application, creates the student record and portal login, and sends notifications.
- **Staff actions:**
  - Verify pending transfers.
  - Refund payments.
  - Send payment reminders.
  - Print receipts.
- **Approved awards:** when an Excellence Award or scholarship is approved for an applicant who has already paid, a partial refund is created automatically.

## Where a real backend plugs in

| Concern | Current (MVP) | Production |
|---|---|---|
| Data | `DB` in `js/storage.js` (localStorage) | Swap each `DB.*` call for `fetch('/api/...')`. `DB` is the only data-access layer. |
| Auth | `Auth.login()` compares plaintext demo passwords | Use `POST /api/auth/login` with hashed passwords and an httpOnly session cookie or JWT, with role checks on the server. |
| Payments | `PaymentService.gateway = ZainpaySimulator` | Build a `ZainpayServerGateway` with the same three methods. It calls **your backend**, and only the backend holds the Zainpay keys and calls the Zainpay sandbox or live API. |
| Payment confirmation | Verified in the browser | `POST /api/webhooks/zainpay` checks the signature and marks the application paid. The UI then polls `/api/payments/verify/:ref`. |
| Notifications | `Notifications.push()` writes a record | A queue sends email and SMS through providers. |
| File uploads | WAEC result is a placeholder (filename only) | Upload to object storage with a signed URL. |
| Certificates | Verified from local data | `GET /api/certificates/:no` backs the public `verify.html`. |

**Never put Zainpay secret credentials in browser JavaScript.**
