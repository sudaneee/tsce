#!/usr/bin/env bash
# Nightly backup (run by tsce-backup.timer): a consistent copy of the SQLite
# database plus the private uploads (WAEC results). Keeps 30 days.
# Copy /var/backups/tsce off the server too — a backup on the same disk
# doesn't survive losing the VPS (see deploy/README.md).
set -euo pipefail

DATA=/var/lib/tsce
DEST=/var/backups/tsce
KEEP_DAYS=30
STAMP=$(date +%Y%m%d-%H%M)
cd /   # may be started from a folder this user can't read (e.g. root's home)

mkdir -p "$DEST"
# .backup is safe while the site is running (unlike copying the file).
sqlite3 "$DATA/db.sqlite3" ".backup '$DEST/db-$STAMP.sqlite3'"
sqlite3 "$DEST/db-$STAMP.sqlite3" "PRAGMA integrity_check;" | grep -qx ok
gzip -f "$DEST/db-$STAMP.sqlite3"

if [ -d "$DATA/private_media" ]; then
    tar -czf "$DEST/private_media-$STAMP.tar.gz" -C "$DATA" private_media
fi

find "$DEST" -name 'db-*.sqlite3.gz' -mtime +$KEEP_DAYS -delete
find "$DEST" -name 'private_media-*.tar.gz' -mtime +$KEEP_DAYS -delete
echo "backup ok: $DEST/db-$STAMP.sqlite3.gz"
