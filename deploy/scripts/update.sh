#!/usr/bin/env bash
# Deploy the latest code from GitHub (main) to the server. Run as root:  sudo bash /srv/tsce/deploy/scripts/update.sh
# Takes a backup first, so a bad migration can be rolled back.
set -euo pipefail

APP=/srv/tsce
cd /   # the tsce user can't read root's home, where this is often started
manage() { sudo -u tsce -H bash -c "cd $APP/backend && .venv/bin/python manage.py $*"; }

echo "==> Backup before updating"
sudo -u tsce "$APP/deploy/scripts/backup.sh"

echo "==> Pull"
sudo -u tsce -H git -C "$APP" pull --ff-only
sudo -u tsce -H git -C "$APP" log --oneline -1

echo "==> Dependencies, migrations, static files"
sudo -u tsce "$APP/backend/.venv/bin/pip" install -q -r "$APP/backend/requirements.txt"
manage migrate --noinput
manage collectstatic --noinput -v 0

echo "==> Services (picks up any changed unit files)"
cp "$APP"/deploy/systemd/tsce-*.service "$APP"/deploy/systemd/tsce-*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl restart tsce-gunicorn
# certbot edits the live nginx file, so it is never overwritten here. Instead, warn when
# the template in the repo has changed since it was last installed/merged by hand.
DOMAIN=$(grep -oP '(?<=^DJANGO_ALLOWED_HOSTS=)[^,]+' "$APP/backend/.env")
TEMPLATE_SUM=$(sha256sum "$APP/deploy/nginx/tsce.conf" | cut -d' ' -f1)
if [ "$TEMPLATE_SUM" != "$(cat /var/lib/tsce/nginx-template.sha256 2>/dev/null)" ]; then
    echo "!! deploy/nginx/tsce.conf has changed since it was installed. Merge the changes into"
    echo "   /etc/nginx/sites-available/tsce by hand (keep certbot's lines), run nginx -t && systemctl reload nginx,"
    echo "   then record it:  sha256sum $APP/deploy/nginx/tsce.conf | cut -d' ' -f1 > /var/lib/tsce/nginx-template.sha256"
fi

echo "==> Health"
sleep 2
curl -fsS --unix-socket /run/tsce/gunicorn.sock -H "Host: $DOMAIN" http://localhost/api/health && echo
manage preflight || echo "!! preflight reported problems (see above)"
