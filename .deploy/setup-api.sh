#!/usr/bin/env bash
set -euo pipefail

BASE=/opt/velmor
APP="$BASE/app"
PASS="$(sed -n 's/^POSTGRES_PASSWORD=//p' "$BASE/.env")"

umask 077
cat > "$APP/packages/api/.env.dev" <<EOF
ENVIRONMENT=dev
DATABASE_URL=postgresql+asyncpg://velmor:${PASS}@127.0.0.1:5433/velmor
REDIS_URL=redis://127.0.0.1:6380/0
LOGFIRE_TOKEN=your-logfire-write-token
EOF
chmod 600 "$APP/packages/api/.env.dev"
echo "wrote $APP/packages/api/.env.dev (mode 600)"

cat > /etc/systemd/system/velmor-api.service <<'UNIT'
[Unit]
Description=Velmor storefront (Proofbasket)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/velmor/app
ExecStart=/opt/velmor/app/.venv/bin/velmor serve --env dev --host 0.0.0.0 --port 8080
Restart=on-failure
RestartSec=5
MemoryMax=512M
CPUQuota=50%

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now velmor-api.service
sleep 5
echo "--- is-active ---"
systemctl is-active velmor-api.service
echo "--- status ---"
systemctl status velmor-api.service --no-pager --lines=12 || true
