# TSCE Platform — Backend Implementation Plan

Turning the approved frontend demo (HTML/CSS/JS + localStorage) into a production system on **Django + SQLite**.

## Decisions (agreed 1 Oct 2026)

| Topic | Decision |
|---|---|
| Timeline | Online application + payment must be live for the **October 2026 cohort** (enrolment 1–12 Oct, classes start 12 Oct). Ship an MVP first; the rest follows after launch. |
| Payments | Real **Zainpay** integration. TSCE has sandbox keys. The simulator stays as a dev-only gateway. |
| Zainpay charges | The **payer pays a ₦300 transaction charge**. It's shown on the invoice and added only to what Zainpay collects, never to fees, receipts or reports. **Bank transfer only.** Both are `.env` settings (`ZAINPAY_PAYER_CHARGE`, `ZAINPAY_CHANNELS`). |
| Hosting | **VPS** (Ubuntu + nginx + gunicorn + systemd + Let's Encrypt). SQLite on persistent disk, daily backups. |
| Learning content | No uploaded lectures or resources in v1. The Learning page is simplified to the module list and progress; the generated "resources" are removed. |
| Email / SMS | No SMS. Email comes later. Until then, Django's file/console email backend is used and in-app notifications work. Password reset is done by admin from the staff portal until email exists. |
| Instructors | Instructors do **not** log in. Admin/staff enter attendance and results. Roles: `applicant`, `student`, `staff`, `admin`. |
| Initial data | Production starts **empty** of people, applications and payments. Seeded: school info (settings) and the 11 real programmes from the flyer. A separate `seed_demo` command exists only for a demo/staging instance. |

## Architecture

```
Browser (existing HTML/CSS/JS)  ──fetch──▶  Django + DRF (/api/...)  ──▶  SQLite (WAL)
     same origin · session cookie + CSRF                                  media/ (WAEC uploads)
                                            /api/webhooks/zainpay  ◀──  Zainpay
```

- **Keep the approved frontend.** Replace `js/storage.js` (localStorage) with `js/api.js` (fetch wrapper). Convert the page modules to `async`. The markup and CSS stay as they are.
- **Same origin.** In production nginx serves the frontend files and proxies `/api/`, `/admin/` and `/media/` to gunicorn. In development Django serves the frontend too, so a single `runserver` works.
- **Auth.** Django sessions (httpOnly cookie) + CSRF token. No JWT.
- **All business rules on the server** in `services.py` modules, wrapped in `transaction.atomic()`. This covers discounts, marking paid, status changes, scholarship approval and refunds, certificate issuing and ID generation. The browser only displays data and sends intents.
- **Django admin** is enabled as the back-office safety net.

## Repository layout

```
tsce-platform/
├── frontend/                  ← existing index.html, pages/, css/, js/, assets/ (moved as-is; relative paths unchanged)
├── backend/
│   ├── manage.py
│   ├── config/                settings (base/dev/prod), urls, wsgi
│   ├── apps/
│   │   ├── core/              SiteSettings singleton, sequences (ID counters), shared utils
│   │   ├── accounts/          User (email login, role), StaffProfile
│   │   ├── programmes/        Programme, Module, Cohort
│   │   ├── admissions/        Application, ApplicationEvent, AwardRequest, discount engine
│   │   ├── payments/          Payment, WebhookEvent, gateways (zainpay, simulator)
│   │   ├── academics/         Enrollment, ModuleProgress, AttendanceSession/Record, Result, Certificate
│   │   └── comms/             Notification, Announcement, SupportTicket, Enquiry
│   └── requirements.txt
├── deploy/                    nginx conf, gunicorn systemd unit, backup script
├── PLAN.md
└── README.md
```

## Data model (as built in Phase 1)

All amounts are whole naira. Display numbers (`TSCE/APP/2026/00001` and so on) come from `core.Sequence` inside a write transaction. Primary keys are ordinary auto IDs.

| App | Model | Notes |
|---|---|---|
| core | **SiteSettings** | Singleton (pk=1). Institution info, certificate signatory, `current_cohort`, `accepting_applications`, discount % and Excellence criteria, payment ref prefix and channels, notification toggles. Gateway keys stay in `.env`. |
| core | **Sequence** | Named counters (`app`, `tx`, `student`, `cert`, `ticket`). |
| accounts | **User** | Email login (stored lower-case, case-insensitive), `full_name`, `role` (`applicant/student/staff/admin`). `is_staff` means Django admin access only. |
| accounts | **StaffProfile** | `staff_no`, title, department, status. `user` is optional: **instructors have no login**. |
| programmes | **Programme** | `slug` is the public id (`fullstack`), plus code, fee, weeks, capacity, nullable `instructor`, status, presentation fields, JSON lists (outcomes, audience, careers, requirements, schedules). Seats taken are computed from enrolments. |
| programmes | **Module** | Ordered per programme. Re-seeding renames in place, so results stay attached. |
| programmes | **Cohort** | Owns the admissions calendar: `start_date`, `enrolment_opens/closes`, `early_bird_deadline`. |
| admissions | **Application** | A snapshot of the applicant's submission, the WAEC file in **private storage**, programme, cohort, schedule, fee and discount fields, `status` (`Pending/Under Review/Accepted/Enrolled/Rejected`) and a separate `payment_status` (`Unpaid/Pending/Paid/Failed/Refunded`). The demo's "Paid" status maps to `payment_status`. |
| admissions | **ApplicationEvent** | The timeline (text, ok, actor). |
| admissions | **AwardRequest** | One per application. Excellence or scholarship; requested/awarded %, interview score, evidence, review fields. |
| payments | **Payment** | `kind` is charge or refund. A refund **must** have a `parent` charge (DB constraint). Also stores status, channel, gateway, `gateway_ref`, `checkout_url`, `gateway_payload`, and verification and refund timestamps. Read-only in admin. |
| payments | **WebhookEvent** | Every webhook is stored raw before processing, with signature validity and processed/error fields. |
| academics | **Student** | The person, one per user. `student_no` and contact details (editable by the student) are copied from the application when payment is confirmed. |
| academics | **Enrollment** | Student × programme × cohort (unique). Schedule, dates, status, a single `progress` %, and `amount_paid`. **Per-module progress is derived** from `progress`, so there's no per-module table to maintain. |
| academics | **AttendanceSession / AttendanceRecord** | One session per programme, cohort and day. One mark per enrolment per session. |
| academics | **Result** | One per enrolment and module. The grade is computed on save. Draft or Published. |
| academics | **Certificate** | Created **when issued** (no reserved numbers). Issued or Revoked. |
| comms | **Notification** | Per user. Staff-wide alerts are fanned out to each staff user so each has their own read state. |
| comms | **Announcement / SupportTicket / Enquiry** | As in the demo, plus author and reply tracking. |

**Private files:** WAEC uploads are saved under `PRIVATE_MEDIA_ROOT`, which nginx never serves. Staff download them through a permission-checked API view.

## Core business rules (move from JS to `services.py`)

| Rule | From (demo) | To |
|---|---|---|
| Discount compute (early bird automatic; excellence/scholarship need review; no stacking, highest wins) | `Discounts` in `applications.js` | `admissions/discounts.py` |
| Create application + award request + applicant login | `Applications.create` | `admissions/services.create_application` |
| Payment confirmed → app paid → enrollment + student login | `Applications.markPaid` | `admissions/services.mark_paid` (called **only** from verified webhook/verify) |
| Staff status change (accept paid ⇒ enrol; reject paid ⇒ refund) | `Applications.setStatus` + drawer | `admissions/services.set_status` |
| Award approval → recompute fee → partial refund if already paid | scholarships `review()` | `admissions/services.review_award` |
| Certificate eligibility (100% modules, ≥75% attendance, ≥50% avg, paid) / issue / revoke | `Students.eligibility`, staff-certificates | `academics/services.py` |
| Grade bands (A ≥80, B ≥70, C ≥60, D ≥50, F) | `Students.grade` | `academics/grading.py` |

## API outline (`/api/…`)

- **Auth**: `POST auth/login`, `POST auth/logout`, `GET auth/me`, `POST auth/change-password`, `POST staff/users/{id}/reset-password` (admin).
- **Public**: `GET settings/public`, `GET programmes`, `GET programmes/{slug}`, `POST applications` (multipart, WAEC file), `POST applications/quote` (discount preview), `GET announcements?audience=Public`, `POST enquiries`, `GET certificates/verify/{no}`.
- **Payments**: `POST payments/initialize` (application → Zainpay checkout URL), `GET payments/verify/{ref}`, `POST webhooks/zainpay`, `GET payments/{ref}/receipt`.
- **Student** (`me/`): dashboard, profile (GET/PATCH), programme + modules, attendance, results, payments, certificate, notifications (+ mark read), announcements, tickets.
- **Staff**: applications (list/filter/detail/status/remind), awards (list/review), payments (list/verify transfer/refund), students (CRUD/detail), programmes (CRUD), attendance (sessions + roster marking), results (gradebook save/publish), certificates (issue/revoke), announcements (CRUD), staff (CRUD, admin), settings (admin), dashboard stats, reports/{name} (+ `?format=csv`), search.

Permissions: `IsApplicant`, `IsStudent`, `IsStaff` (staff+admin), `IsAdmin`. Students only ever see their own records. This is enforced in querysets, not just the UI.

## Phases

### MVP — live for the October cohort

**Phase 0 — Setup**
- [x] `git init`, `.gitignore`, move frontend into `frontend/`
- [x] Django project `backend/` (settings split dev/prod, `.env` via `django-environ`), DRF, SQLite WAL
- [x] Django serves `frontend/` in dev; `js/api.js` fetch wrapper with CSRF + error handling
- [x] Custom `User` model (email login, role) — must exist before the first migration
- [x] Uniform API error shape, `/api/health`, `/api/auth/csrf`, foundation tests

**Phase 1 — Data layer**
- [x] All models + migrations + Django admin registrations (20 models)
- [x] `seed_school` command: SiteSettings from flyer + 11 programmes / 85 modules + October cohort (idempotent; `--update` resets programmes to the flyer)
- [x] Model tests: sequences, singleton, grading, derived module progress, constraints, seed behaviour
- [ ] ~~`seed_demo`~~ moved to Phase 5b, so demo data is created through the real services instead of duplicating their logic

**Phase 2 — Auth**
- [x] `auth/login` (CSRF-protected, rate-limited 10/min per IP, "keep me signed in"), `auth/logout`, `auth/me`, `auth/change-password`
- [x] Role permissions (`IsApplicant`, `IsStudent`, `IsPortalStaff`, `IsAdmin`); 401 = sign in again, 403 = not allowed
- [x] Admin password reset (`staff/users/{id}/reset-password`) → temporary password + forced change at next login (no email yet)
- [x] `auth.js` on server sessions; router loads the user once per page; demo logins, DEMO chip and Explore tour removed; Change password in the portal user menu
- [x] 14 auth API tests + browser test (headless Edge) of login, redirects, logout, session expiry, forced password change

**Phase 3 — Public site & application**
- [x] `GET /api/site`: public settings and the programme catalogue with live seat counts, loaded once per page (`Site`). Early-bird status and the admissions window are decided by the server in Lagos time.
- [x] Application wizard → `POST /api/applications` (multipart). Server validation (Nigerian phone, age, WAEC rules, schedule offered by the programme), WAEC upload checked by content and kept in private storage, admissions window and capacity enforced, award requests, applicant account created and signed in. Existing accounts must give their password, and duplicate applications are refused.
- [x] `GET /api/applications/{number}` for the owner or staff
- [x] Contact enquiries (`POST /api/enquiries`), public news (`GET /api/announcements/public`), certificate verify (`GET /api/certificates/verify?no=`)
- [x] Removed: autofill demo applicant, demo certificate numbers, invented home-page statistics and testimonials (hidden until TSCE supplies real ones). Application drafts moved to sessionStorage, which suits shared computers.
- [x] Browser tests now live in the repo: `bash e2e/run.sh` (auth + public suites)

**Phase 4 — Zainpay**
- [x] `ZainpayGateway` ported from the Glittering Field Academy integration (live-tested): initialize → hosted checkout → verify v2, with both success shapes handled, the ambiguous "Txn not found" response never treated as final, and the reconcile endpoint as fallback. Keys only in `.env`.
- [x] Webhook `POST /api/payments/zainpay/webhook`: stored raw (`WebhookEvent`), HMAC-SHA256 `Zainpay-Signature` checked, payment **re-verified via the API** (body never trusted), idempotent, always 200 except a bad signature
- [x] Callback `GET /api/payments/zainpay/callback?txnRef=` → success page or back to the invoice (failed/pending). Missing `txnRef` is recovered only from the same browser session, never by guessing.
- [x] `reconcile_payments` command for cron (every 5 min) as the safety net
- [x] Payment confirmed → application Paid, Student record + student number, Enrollment (Admission Pending, or Active if already accepted), account upgraded to student, notifications. Duplicate payments are flagged to staff for refund, never double-enrolled.
- [x] Re-quote at checkout (early bird depends on the **payment** date) and capacity re-checked
- [x] `payment.html` / `success.html` rewired: invoice → Zainpay hosted page → result; pending payments re-checked automatically; receipt built from server data
- [x] Simulator gateway (`PAYMENT_GATEWAY=simulator`) with a local checkout page for development and demos. Production refuses to start with it unless `ALLOW_PAYMENT_SIMULATOR=true`.
- [x] 22 payment unit tests + browser suite `e2e/test_payments.py`
- [ ] **Sandbox run with TSCE's real Zainpay keys** (card + transfer, webhook delivery to a public URL, reconcile). Confirm: `paymentChannels` values, the webhook event names, and that the paid amount is enforced on transfers.

**Phase 5 — Staff admissions & finance**
- [ ] Applications list/filters/detail drawer/lifecycle actions/print
- [ ] Award (Excellence/Scholarship) review with refund calculation
- [ ] Payments list, verify pending transfer, refund, reminders
- [ ] Staff accounts management + admin password reset; Settings page (admissions dates, early-bird deadline, accepting applications)

**Phase 5b — Demo/staging data**
- [ ] `seed_demo` command (staging only): builds demo applicants, payments and students by calling the real services

**Before go-live (carried from earlier phases)**
- [ ] Staff portal pages not yet wired to the API still show the old browser demo data. At launch, hide or disable every page that isn't wired yet (students, attendance, assessments, certificates, reports, etc.).
- [ ] Student portal shows an "almost ready" placeholder until Phase 7. Decide what paid students see at launch (at minimum: admission status + receipt).

**Phase 6 — Deploy (VPS)**
- [ ] nginx + gunicorn + systemd, HTTPS (Let's Encrypt), `collectstatic`, media dir permissions
- [ ] cron: `reconcile_payments` every 5 minutes
- [ ] Production settings (DEBUG off, secure cookies, HSTS, allowed hosts), daily SQLite + media backup (cron, `sqlite3 .backup`)
- [ ] Zainpay sandbox end-to-end test → switch to live keys

### After launch

**Phase 7 — Student portal**: dashboard, profile, programme (simplified Learning), attendance, results, payments, certificate, announcements, support, settings.

**Phase 8 — Academics (staff)**: students CRUD, programmes CRUD, attendance marking, gradebook (draft/publish), certificates issue/revoke/print, announcements.

**Phase 9 — Dashboards & reports**: real aggregates (no baselines), 6 reports with filters + CSV export, global search (Ctrl K).

**Phase 10 — Email**: once TSCE provides the mailbox, configure SMTP, add templates for application received / payment / accepted / result / certificate, and enable self-service password reset.

Throughout: tests for discounts, mark-paid, status transitions, award refunds, webhook idempotency and permission boundaries.

## Open items / needs from client

- Zainpay sandbox **public key (JWT), secret key, zainbox code** (to `.env`, never committed); live keys before go-live. Register the webhook URL `https://<domain>/api/payments/zainpay/webhook` in the Zainpay dashboard.
- VPS access + domain/DNS (`tsce.edu.ng` subdomain?).
- Sending email account (later).
- **Early-bird deadline**: the flyer date (before 1 Oct 2026) has already passed. Does TSCE want to extend it? It is a setting in Staff → Settings, so no code change is needed either way.
- Real staff list (names, titles, emails) for the initial admin/staff accounts and programme instructors. The director's name is also needed for certificates.
- **Admissions dates conflict:** the flyer opens enrolment on **1 October** but the early-bird discount needs payment **before 1 October**, so nobody could ever qualify. Confirm the real enrolment opening date (and whether early bird is still on offer). Both are editable settings.
- Real home-page statistics and testimonials, or keep those sections hidden.
- Confirm the event dates on the News page (intake exams 3–7 Oct, orientation 10 Oct). They came from the demo, not the flyer.
