#!/usr/bin/env bash
# Browser (end-to-end) tests against a real dev server on a throwaway database.
#
#   One-time:  python -m venv .e2e/venv && .e2e/venv/Scripts/pip install -r e2e/requirements.txt
#              (Linux/macOS: .e2e/venv/bin/pip …; then `playwright install chromium` and E2E_BROWSER=chromium)
#   Run all:   bash e2e/run.sh
#   Run one:   bash e2e/run.sh public
#
# Each suite = e2e/setup_<name>.py (fills the fresh DB) + e2e/test_<name>.py (drives the browser).
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$REPO/.e2e/work"
PORT="${E2E_PORT:-8765}"
export E2E_BASE="http://localhost:$PORT" PYTHONIOENCODING=utf-8
export SQLITE_PATH="$WORK/db.sqlite3" CACHE_DIR="$WORK/cache" PRIVATE_MEDIA_ROOT="$WORK/private"
# Browser tests always use the built-in simulator, never a real gateway.
export PAYMENT_GATEWAY=simulator

PY="$REPO/backend/.venv/Scripts/python"; [ -x "$PY" ] || PY="$REPO/backend/.venv/bin/python"
TPY="$REPO/.e2e/venv/Scripts/python";   [ -x "$TPY" ] || TPY="$REPO/.e2e/venv/bin/python"

stop_server() {
    [ -n "${SERVER_PID:-}" ] && kill "$SERVER_PID" 2>/dev/null
    # Windows: make sure the Python child is gone too.
    command -v powershell >/dev/null && powershell -NoProfile -Command \
        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*runserver $PORT*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force }" >/dev/null 2>&1
    SERVER_PID=""
}
trap stop_server EXIT

run_suite() {
    local name="$1"
    echo "=== $name ==="
    stop_server
    rm -rf "$WORK" && mkdir -p "$WORK"
    (cd "$REPO/backend" && "$PY" manage.py migrate -v 0) || return 1
    # Executed as one script (piping into `shell` runs it line by line, which breaks on loops).
    (cd "$REPO/backend" && "$PY" manage.py shell -c "exec(open('../e2e/setup_$name.py', encoding='utf-8').read())" 2>&1 | tee "$WORK/setup.log" | grep -q "setup done")         || { echo "setup failed:"; cat "$WORK/setup.log"; return 1; }
    (cd "$REPO/backend" && exec "$PY" manage.py runserver "$PORT" --noreload > "$WORK/server.log" 2>&1) &
    SERVER_PID=$!
    for _ in $(seq 1 30); do curl -s -o /dev/null "$E2E_BASE/api/health" && break; sleep 1; done
    "$TPY" "${E2E_SCRIPT:-$REPO/e2e/test_$name.py}"
}

suites=("$@"); [ ${#suites[@]} -eq 0 ] && suites=(auth public payments)
failed=0
for s in "${suites[@]}"; do run_suite "$s" || failed=1; done
exit $failed
