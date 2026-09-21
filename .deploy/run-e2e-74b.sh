#!/usr/bin/env bash
set -euo pipefail
cd /opt/velmor/app
export PATH="$HOME/.local/bin:$PATH"
sed -i 's/\r$//' .deploy/e2e-purchase.sh
export STUB_WEBHOOK_SECRET="$(grep '^STUB_WEBHOOK_SECRET=' packages/api/.env.dev | cut -d= -f2-)"
bash .deploy/e2e-purchase.sh