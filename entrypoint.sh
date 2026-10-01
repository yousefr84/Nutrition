#!/bin/sh
set -e

mkdir -p /app/staticfiles /app/media
[ -z "${POSTGRES_HOST:-}" ] && mkdir -p /app/data

# Volume mounts are root-owned by default; fix ownership then drop privileges.
if [ "$(id -u)" = "0" ]; then
    chown -R app:app /app/staticfiles /app/media
    [ -z "${POSTGRES_HOST:-}" ] && chown -R app:app /app/data
    # Re-exec as app with intact argv (su -c would break quoting).
    exec runuser -u app -- "$0" "$@"
fi

wait_for_redis() {
    redis_url="${CELERY_BROKER_URL:-redis://redis:6379/0}"
    hostport=$(echo "$redis_url" | sed -E 's|^redis://([^/]+).*|\1|')
    host=$(echo "$hostport" | cut -d: -f1)
    port=$(echo "$hostport" | cut -d: -f2)
    [ -z "$port" ] && port=6379

    echo "[entrypoint] Waiting for redis at ${host}:${port}..."
    i=0
    until python -c "import socket;s=socket.socket();s.settimeout(2);s.connect(('${host}',${port}));s.close()" 2>/dev/null
    do
        i=$((i + 1))
        if [ "$i" -gt 60 ]; then
            echo "[entrypoint] Redis timeout"
            exit 1
        fi
        sleep 1
    done
    echo "[entrypoint] Redis ready."
}

enable_wal() {
    [ -n "${POSTGRES_HOST:-}" ] && return 0
    DB="${DB_PATH:-/app/data/db.sqlite3}"
    mkdir -p "$(dirname "$DB")"
    if [ -f "$DB" ]; then
        python - "$DB" <<'PY'
import sqlite3, sys
db = sys.argv[1]
con = sqlite3.connect(db)
con.execute("PRAGMA journal_mode=WAL;")
con.execute("PRAGMA busy_timeout=5000;")
con.commit()
con.close()
PY
    fi
}

wait_for_redis

ROLE="${RUN_ROLE:-web}"

if [ "$ROLE" = "celery" ]; then
    enable_wal
    echo "[entrypoint] Starting Celery..."
    exec "$@"
fi

echo "[entrypoint] Running migrations..."
python manage.py migrate --noinput

echo "[entrypoint] Collecting static..."
python manage.py collectstatic --noinput

enable_wal

echo "[entrypoint] Starting application..."
exec "$@"
