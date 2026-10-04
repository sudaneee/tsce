# Deploying the TSCE portal to a VPS

One Ubuntu server runs everything: **nginx** serves the website files and HTTPS and passes `/api/` and `/admin/` to **Django** (gunicorn). Data lives in **SQLite**. Two **systemd timers** confirm missed payments every 5 minutes and take a backup every night.

```
Internet ──HTTPS──▶ nginx ─┬─ /            → /srv/tsce/frontend   (website + portals, plain files)
                           ├─ /static/     → /var/www/tsce/static (Django admin assets)
                           └─ /api/ /admin → gunicorn (unix socket) → Django → /var/lib/tsce/db.sqlite3
Zainpay ──webhook──▶ /api/payments/zainpay/webhook
```

| Path | What |
|---|---|
| `/srv/tsce` | The code (a git clone of the repo), owned by the `tsce` user |
| `/srv/tsce/backend/.env` | **Secrets and settings** (mode 600). Never committed. |
| `/var/lib/tsce/db.sqlite3` | The database |
| `/var/lib/tsce/private_media` | WAEC result uploads. **Never served by nginx.** Staff download them through Django. |
| `/var/backups/tsce` | Nightly backups, kept for 30 days |

## What you need first

1. **A VPS** running Ubuntu 22.04 or 24.04. 1 vCPU, 1–2 GB RAM and 25 GB disk is plenty. You need root (or sudo) SSH access.
2. **A domain**, e.g. `tsce.com.ng`, with a DNS **A record** pointing to the VPS IP address. Set this up first, because HTTPS needs it.
3. **A Gmail address with an App Password** for outgoing email (Google Account → Security → 2-Step Verification → App passwords).
4. **Zainpay keys** from the merchant dashboard: the public key (a JWT), the secret key and the zainbox code. Start with sandbox keys.

## 1. Let the server read the repository

The repo is private, so give the server a read-only **deploy key**:

```bash
sudo adduser --system --group --no-create-home --home /srv/tsce --shell /usr/sbin/nologin tsce
sudo mkdir -p /srv/tsce && sudo chown tsce:tsce /srv/tsce
sudo -u tsce -H ssh-keygen -t ed25519 -N "" -f /srv/tsce/.ssh/id_ed25519 -C "tsce-vps"
sudo cat /srv/tsce/.ssh/id_ed25519.pub
```

On GitHub, open the repository → **Settings → Deploy keys → Add deploy key**, paste the key and leave "write access" **off**. Then accept GitHub's host key once with `sudo -u tsce -H ssh -T git@github.com` (answer `yes`).

> Alternatively, use an HTTPS URL with a fine-grained read-only GitHub token instead of a deploy key.

## 2. Run the setup script

```bash
# from your computer (the repo is private, so copy the script over):
scp deploy/scripts/bootstrap.sh root@YOUR-VPS-IP:/root/
# on the server:
sudo bash /root/bootstrap.sh tsce.com.ng git@github.com:sudaneee/tsce.git you@example.com
```

The script:
- installs the packages;
- creates the folders above;
- clones the code and sets up Python;
- generates `backend/.env` with a fresh secret key and all the paths;
- migrates the database and loads the school data (`seed_school`);
- installs the services and timers, and adds its own nginx site;
- obtains the HTTPS certificate.

It is safe to run again, and safe on a server that already hosts other sites. It never upgrades existing packages, never edits or removes other nginx sites (and rolls back if the nginx test fails), and never changes the firewall. Make sure ports 80 and 443 are open.

## 3. Fill in the secrets

```bash
sudo nano /srv/tsce/backend/.env
```

Set `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` (the 16-character app password), `DEFAULT_FROM_EMAIL` (e.g. `TSCE Admissions <you@gmail.com>`), `ZAINPAY_PUBLIC_KEY`, `ZAINPAY_SECRET_KEY` and `ZAINPAY_ZAINBOX_CODE`. Then:

```bash
sudo systemctl restart tsce-gunicorn
sudo tsce-manage createsuperuser          # the first admin (email + password)
sudo tsce-manage preflight --send-test-email you@example.com
```

`preflight` must end with **READY**. Fix anything marked ✘. The warnings (⚠) say what's still open, such as sandbox mode.

**In the Zainpay dashboard**, set the webhook URL to `https://tsce.com.ng/api/payments/zainpay/webhook`.

**In the portal** (Staff → Settings): enter the director's name (it's printed on certificates), check the admissions dates and the early-bird deadline, and add your staff (Staff → Add staff).

## 4. Sandbox test (before real money)

With `ZAINPAY_ENVIRONMENT=sandbox`:

1. Register a parent account using a real inbox you can read, and click the verification link.
2. Apply for a child. The child is admitted straight away and you land on the programme-fee invoice (programme fee + ₦5,000 application fee + ₦300 charge).
3. Pay it with Zainpay's **sandbox** transfer details. You should come back to the success page, and the child should show as **Enrolled** with a student number.
4. Apply again requesting the Excellence Award, then approve it in Staff → Excellence Awards and check that the tuition is halved (the ₦5,000 application fee is not discounted).
5. In the Django admin (`/admin/` → Webhook events), confirm webhooks arrived with **signature valid** ticked.
6. Run `sudo systemctl start tsce-reconcile` and check `journalctl -u tsce-reconcile -n 20`.

Then clear the test data (see "Starting clean" below) and switch to live.

## 5. Go live

```bash
sudo nano /srv/tsce/backend/.env    # ZAINPAY_ENVIRONMENT=live and the LIVE keys
sudo systemctl restart tsce-gunicorn
sudo tsce-manage preflight
```

Make one small real payment to confirm it works end to end.

### Starting clean after testing

The test applicants, payments and accounts should not remain in the live system. Before any real applicant arrives:

```bash
sudo systemctl stop tsce-gunicorn
sudo mv /var/lib/tsce/db.sqlite3 /var/backups/tsce/db-sandbox-test.sqlite3
sudo rm -f /var/lib/tsce/db.sqlite3-wal /var/lib/tsce/db.sqlite3-shm
sudo rm -rf /var/lib/tsce/private_media/*
sudo tsce-manage migrate && sudo tsce-manage seed_school && sudo tsce-manage createsuperuser
sudo systemctl start tsce-gunicorn
```

Then re-enter the settings, the director's name and the staff accounts.

## Everyday operations

| Task | Command |
|---|---|
| Deploy the latest code | `sudo bash /srv/tsce/deploy/scripts/update.sh` (backs up first, then pull, migrate, restart and health check) |
| Run any Django command | `sudo tsce-manage <command>` |
| App logs | `journalctl -u tsce-gunicorn -f` |
| Payment reconciliation log | `journalctl -u tsce-reconcile -n 50` |
| Timers | `systemctl list-timers 'tsce-*'` |
| Back up now | `sudo systemctl start tsce-backup` |
| Reset a forgotten password | Staff → Staff → *Reset password*, or `sudo tsce-manage changepassword email@x` |

### Backups: also copy them off the server

The nightly backups sit on the same disk as the database, so they won't survive losing the VPS. Copy `/var/backups/tsce` somewhere else daily: your provider's snapshot feature, `rclone` to Google Drive, or `scp` from another machine.

**To restore:**

```bash
sudo systemctl stop tsce-gunicorn
gunzip -c /var/backups/tsce/db-YYYYMMDD-HHMM.sqlite3.gz | sudo -u tsce tee /var/lib/tsce/db.sqlite3 >/dev/null
sudo rm -f /var/lib/tsce/db.sqlite3-wal /var/lib/tsce/db.sqlite3-shm
sudo -u tsce tar -xzf /var/backups/tsce/private_media-YYYYMMDD-HHMM.tar.gz -C /var/lib/tsce
sudo systemctl start tsce-gunicorn
```

## Troubleshooting

| Symptom | Check |
|---|---|
| 502 Bad Gateway | `systemctl status tsce-gunicorn`. Usually a typo in `.env`, so look at `journalctl -u tsce-gunicorn -n 50`. |
| "PAYMENT_GATEWAY=simulator in production" | `.env` is missing `PAYMENT_GATEWAY=zainpay`. |
| Verification emails don't arrive | `sudo tsce-manage preflight --send-test-email you@x`. Gmail needs an *App Password*, not the account password. |
| Payments stuck on "confirming" | Zainpay can be slow to confirm transfers. The 5-minute timer picks them up. Check `journalctl -u tsce-reconcile`. |
| Certificate didn't issue | Is DNS pointing here? Run `dig +short tsce.com.ng`, then re-run `sudo certbot --nginx -d tsce.com.ng --redirect`. |
