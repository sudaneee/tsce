# TSCE Digital Platform

Website, admissions and portals for **Trust Skill Acquisition Centre of Excellence (TSCE), Zaria** — live at
<https://tsce.com.ng>. Django + SQLite; every page is rendered by Django on the server. See [PLAN.md](PLAN.md) for the
decisions and history, and [deploy/README.md](deploy/README.md) for the server.

## How it fits together

```
Browser ──▶ nginx ──▶ Django (gunicorn) ──▶ SQLite (WAL)
              │          backend/apps/web   pages: public site, sign-in, 5-step application, payments,
              │                             staff portal (/staff/), student portal (/student/)
              │          /api/health, /api/payments/zainpay/{callback,webhook}   ◀── Zainpay
              └─ /css /js/site.js /assets /static   (files)
```

- **All business rules live on the server**: views call the services in `backend/apps/*/services.py`
  (admissions, payments, accounts, academics). Templates only display what the views computed.
- **JavaScript is optional**: `frontend/js/site.js` adds animations, countdowns, the FAQ accordion and instant
  catalogue filtering. Menus, filters, pop-ups and every form work without it.
- **Frontend files**: `frontend/css/` (design system: `main.css`, `dashboard.css`, `responsive.css`, `web.css`),
  `frontend/js/site.js`, `frontend/assets/` (official logo). CSS links carry a version so caches refresh on release.

| Area | Addresses | Code |
|---|---|---|
| Public site | `/`, `/pages/{about,programmes,admissions,news,contact,verify}.html` | `apps/web/views/public.py` |
| Accounts | `/account/{login,register,verify-email,password}/` | `apps/web/views/auth.py` |
| Application (5 steps) | `/apply/1…4/`, `/apply/done/<number>/` | `apps/web/views/apply.py` |
| Applicant | `/my-applications/`, `/pay/<number>/`, `/payments/<ref>/[receipt/]` | `apps/web/views/applicant.py` |
| Staff portal | `/staff/…` (applications, awards, payments, support, team, settings) | `apps/web/views/staff.py` |
| Student portal | `/student/<id>/…` (programme, attendance, results, certificate, payments, support) | `apps/web/views/student.py` |
| Zainpay | `/api/payments/zainpay/callback`, `/api/payments/zainpay/webhook` | `apps/payments/views.py` |

## Development

Requires Python 3.12+. From the repo root:

```bash
python -m venv backend/.venv
backend/.venv/Scripts/pip install -r backend/requirements.txt   # Linux/macOS: backend/.venv/bin/pip
cd backend
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py seed_school                      # school settings, current cohort, 11 programmes
.venv/Scripts/python manage.py createsuperuser                  # admin role (staff portal + Django admin)
.venv/Scripts/python manage.py runserver                        # http://localhost:8000
.venv/Scripts/python manage.py test apps                        # unit + page tests
```

- In development Django also serves `frontend/` (one server, one origin). In production nginx serves the files and
  passes the page addresses above to gunicorn (`deploy/nginx/tsce.conf`).
- Configuration comes from `backend/.env` (copy `backend/.env.example`). Development works without one.

### Payments (Zainpay)

- `PAYMENT_GATEWAY=simulator` (the development default) replaces Zainpay's hosted checkout with a local page where you
  choose *Pay*, *Decline* or *Cancel*. Production refuses the simulator unless `ALLOW_PAYMENT_SIMULATOR=true`.
- `PAYMENT_GATEWAY=zainpay` with `ZAINPAY_ENVIRONMENT=sandbox|live` and the keys in `backend/.env`. Register
  `https://<domain>/api/payments/zainpay/webhook` as the webhook URL in the Zainpay dashboard.
- `reconcile_payments` runs every 5 minutes (systemd timer) and confirms payments whose callback and webhook were missed.
- Zainpay's API quirks are documented at the top of `backend/apps/payments/gateways.py`.
- **Never put Zainpay secret credentials in browser code or in git.**

### Browser tests

End-to-end tests drive headless Edge against a dev server on a throwaway database (`.e2e/work/`), with "today"
pinned to 1 October 2026:

```bash
python -m venv .e2e/venv && .e2e/venv/Scripts/pip install -r e2e/requirements.txt   # once
bash e2e/run.sh            # all suites (auth, public, payments, journey, staff)
bash e2e/run.sh journey    # one suite: e2e/setup_journey.py + e2e/test_journey.py
```
