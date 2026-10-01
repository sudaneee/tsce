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

## Revised admissions flow (decided 1 Oct 2026, replaces the demo's "pay full fee on applying")

```
Register (Student account for yourself, or Parent account for your children)
  → verify email (link sent by email)
  → fill application (a parent adds one application per child)
  → pay the APPLICATION FEE (₦5,000 + ₦300 Zainpay charge, non-refundable, one per application)
  → ┬─ no award requested:  ADMITTED automatically → pay PROGRAMME FEE → ENROLLED
    └─ Excellence Award requested (WAEC 2020+ with 5 A's): AWAITING VERIFICATION
         → applicant visits TSCE with the result → staff approve (50%) or decline the award
         → ADMITTED (award approved: 50% off; declined: normal price) → pay programme fee → ENROLLED
```

- **Two payments:** the application fee, and the programme fee (₦45,000/₦50,000). Discounts apply only to the programme fee and don't stack (highest wins): an approved Excellence Award (50%) or the early bird (15%, judged on the programme-fee payment date).
- **The Performance Scholarship no longer exists.** Qualifying applicants may skip the award and be admitted automatically.
- **Seats** are only taken when the programme fee is paid. There's no automatic lapse of unpaid admissions (staff can reject manually).
- **Accounts:** email + password, email must be verified before applying. A Parent account manages everything for its children (applications, payments, and later the child's portal view). A self-applicant's account becomes their student login on enrolment.
- **Refunds** are only needed for mistakes such as a double payment. No award refunds, since awards are decided before the programme fee is paid.
- **Email:** Gmail SMTP with an app password, configured in `.env` (same setup as the Glittering project). Emails are printed to the console in development until it's configured.

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
| accounts | **User** | Email login (stored lower-case, case-insensitive), `full_name`, `phone`, `role` (`applicant/parent/student/staff/admin`), `email_verified_at`. `is_staff` means Django admin access only. |
| accounts | **StaffProfile** | `staff_no`, title, department, status. `user` is optional: **instructors have no login**. |
| programmes | **Programme** | `slug` is the public id (`fullstack`), plus code, fee, weeks, capacity, nullable `instructor`, status, presentation fields, JSON lists (outcomes, audience, careers, requirements, schedules). Seats taken are computed from enrolments. |
| programmes | **Module** | Ordered per programme. Re-seeding renames in place, so results stay attached. |
| programmes | **Cohort** | Owns the admissions calendar: `start_date`, `enrolment_opens/closes`, `early_bird_deadline`. |
| admissions | **Application** | A snapshot of the applicant's submission, the WAEC file in **private storage**, programme, cohort, schedule, fee and discount fields, `status` (`Pending/Under Review/Accepted/Enrolled/Rejected`) and a separate `payment_status` (`Unpaid/Pending/Paid/Failed/Refunded`). The demo's "Paid" status maps to `payment_status`. |
| admissions | **ApplicationEvent** | The timeline (text, ok, actor). |
| admissions | **AwardRequest** | One per application. Excellence or scholarship; requested/awarded %, interview score, evidence, review fields. |
| payments | **Payment** | `purpose` is `application_fee` or `programme_fee`; `kind` is charge or refund. A refund **must** have a `parent` charge (DB constraint). Also stores status, channel, gateway, `gateway_ref`, `checkout_url`, `gateway_payload`, and verification and refund timestamps. Read-only in admin. |
| payments | **WebhookEvent** | Every webhook is stored raw before processing, with signature validity and processed/error fields. |
| academics | **Student** | The enrolled person, created when the programme fee is paid. Either `user` (a self-applicant's own login) or `guardian` (the parent account, for a child with no login). |
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
- [ ] ~~`seed_demo`~~ moved to Phase 5b (since skipped)

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
- [x] Staff dashboard on live numbers: applications by status, admitted, enrolled, awards to verify, money collected, seats taken per programme, latest applications
- [x] Applications: filters, search, status chips, CSV export, detail drawer (applicant + parent account, fees, payments, history, private WAEC result), send reminder, reject (with reason, emailed)
- [x] Excellence Awards: verification queue → approve (50%) / decline → admitted either way
- [x] Payments: every transaction, both fees, duplicates flagged, "Check with Zainpay", **record refund** (duplicates only, after a manual bank transfer), receipts, CSV
- [x] Staff accounts (admin): add with or without login (instructors), temporary password + forced change, edit, deactivate, reset password; no self-lockout
- [x] Settings (admin): institution, admissions calendar + application fee, discounts, notifications, start a new intake; gateway and email shown read-only (they're set in `.env`)
- [x] Notification bell and Ctrl K search on the server; sidebar badges for awards to verify and duplicate payments
- [x] Staff pages not yet on the API (students, programmes, attendance, assessments, certificates, announcements, reports) are marked "soon" and show "Coming soon" instead of demo data
- [x] Tests: 84 unit tests; browser suite `staff` (28 checks)

**Phase 5b — Demo/staging data** *(skipped, optional, 1 Oct 2026)*
- Not needed for launch: production starts empty, and the browser suites set up their own data. For a demo or training copy, run a staging server with the payment simulator and register a few test accounts. Revisit only if a permanent demo server full of sample records is ever wanted.

**Phase 3b — Accounts, email verification & two-step admissions** (rework of Phases 3–4 for the revised flow)
- [x] Register as Student (self) or Parent → verification email (signed link, 48 h) → verify signs you in once; login refused until verified (a new link is sent); resend; nothing reveals whether an email is registered
- [x] Email via Gmail SMTP with an app password (same as Glittering), best-effort sending; console in development. Key admissions events are emailed as well as notified in-app.
- [x] Applications belong to the signed-in account; a parent applies per child (child's email optional); duplicates checked per child + programme + cohort
- [x] Application fee (₦5,000 setting, + ₦300 Zainpay charge) → **auto-admitted**, or **Awaiting Verification** for an Excellence Award request
- [x] Staff award decision `POST /api/staff/applications/{no}/award` (approve → 50%, decline → full price; admits either way). Staff screen in Phase 5.
- [x] Programme fee (re-priced at payment: best of award / early bird) → **Enrolled**, student number, seat taken; parent-managed children have no login of their own (`Student.guardian`)
- [x] Performance Scholarship removed everywhere (model, settings, UI, public pages)
- [x] Pages: register, verify-email, My applications (per child: progress tracker + next action); wizard, payment and success pages handle both fees
- [x] Tests: 72 unit tests; browser suites auth, public, payments, **journey** (register → verify → two children → award approval → both enrolled)

**Before go-live (carried from earlier phases)**
- [x] Staff portal pages not yet wired to the API are disabled ("Coming soon") instead of showing demo data.
- [ ] Student portal shows an "almost ready" placeholder until Phase 7. Decide what paid students see at launch (at minimum: admission status + receipt).

**Phase 6 — Deploy (VPS)**
- [x] Deployment kit in `deploy/` (guide: `deploy/README.md`): nginx site (frontend files + `/api` and `/admin` proxy, private uploads never served, dotfiles denied), gunicorn on a unix socket under hardened systemd, `bootstrap.sh` (one-time server setup incl. firewall + Let's Encrypt), `update.sh` (backup → pull → migrate → restart → health check), `tsce-manage` helper
- [x] systemd timers: `reconcile_payments` every 5 minutes; nightly SQLite (`.backup` + integrity check) + private-uploads backup, 30 days kept
- [x] `manage.py preflight [--send-test-email]`: go-live checklist (secrets, HTTPS/hosts/CSRF, migrations, school data, admin, Zainpay keys + webhook URL, email, private-file safety, static files)
- [x] `manage.py` picks production settings from `backend/.env` on the server
- [x] **Deployed 1 Oct 2026** to the shared VPS (69.10.44.126) at **https://tsce.com.ng** (+ www), behind Cloudflare; Let's Encrypt certificate; all other sites on the server verified unaffected; timers and backup verified
- [ ] Owner to finish on the server: Zainpay keys + Gmail app password in `/srv/tsce/backend/.env`, `systemctl restart tsce-gunicorn`, `tsce-manage createsuperuser`, `tsce-manage preflight --send-test-email …`; Zainpay webhook URL; Cloudflare SSL mode "Full (strict)"
- [ ] Zainpay sandbox end-to-end test (guide §4) → clear test data → live keys
- [ ] Off-server copy of `/var/backups/tsce` (provider snapshots, rclone, or scp)

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
