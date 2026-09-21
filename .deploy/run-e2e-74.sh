#!/usr/bin/env bash
set -euo pipefail
cd /opt/velmor/app
export PATH="$HOME/.local/bin:$PATH"
curl -fsS http://127.0.0.1:8080/health
echo
curl -fsS http://127.0.0.1:8080/checkout/providers
echo
uv run velmor seed-disclosure --env dev
curl -fsS http://127.0.0.1:8080/checkout/disclosure | python3 -c 'import json,sys; d=json.load(sys.stdin); print("complete", d["complete"]); print("missing", d["missing"])'
sed -i 's/\r$//' .deploy/e2e-purchase.sh
export STUB_WEBHOOK_SECRET="$(grep '^STUB_WEBHOOK_SECRET=' packages/api/.env.dev | cut -d= -f2-)"
bash .deploy/e2e-purchase.sh