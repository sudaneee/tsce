#!/usr/bin/env bash
# Deploy the latest code from GitHub (main) to the server. Run as root:  sudo bash /srv/tsce/deploy/scripts/update.sh
# Takes a backup first, so a bad migration can be rolled back.
set -euo pipefail

APP=/srv/tsce
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
sed "s/__DOMAIN__/$(grep -oP '(?<=^DJANGO_ALLOWED_HOSTS=)[^,]+' $APP/backend/.env)/g" "$APP/deploy/nginx/tsce.conf" > /tmp/tsce.nginx.new
# certbot edits the live nginx file, so only report template drift instead of overwriting it.
if ! diff -q <(grep -v ssl /tmp/tsce.nginx.new) <(grep -v -e ssl -e '# managed by Certbot' /etc/nginx/sites-available/tsce) >/dev/null 2>&1; then
    echo "!! deploy/nginx/tsce.conf changed — review and merge it into /etc/nginx/sites-available/tsce by hand"
fi

echo "==> Health"
sleep 2
curl -fsS --unix-socket /run/tsce/gunicorn.sock http://localhost/api/health && echo
manage preflight || echo "!! preflight reported problems (see above)"
