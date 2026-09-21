#!/usr/bin/env bash
set -euo pipefail
cd /opt/velmor/app
git fetch /tmp/velmor-74.bundle feat/add-storefront-commerce:refs/heads/deploy-74
git checkout deploy-74
git log -1 --oneline
if ! grep -q '^STUB_WEBHOOK_SECRET=' packages/api/.env.dev; then
  echo 'STUB_WEBHOOK_SECRET=e2e-stub-webhook-hmac-secret-dev-only' >> packages/api/.env.dev
fi
grep '^STUB_WEBHOOK_SECRET=' packages/api/.env.dev | sed 's/=.*/=***/'
export PATH="$HOME/.local/bin:$PATH"
uv sync
systemctl restart velmor-api.service
sleep 4
systemctl is-active velmor-api.service
curl -fsS http://127.0.0.1:8080/health
echo
curl -fsS http://127.0.0.1:8080/checkout/providers
echo
uv run velmor seed-disclosure --env dev
curl -fsS http://127.0.0.1:8080/checkout/disclosure | python3 -c 'import json,sys; d=json.load(sys.stdin); print("complete", d["complete"]); print("missing", d["missing"])'
