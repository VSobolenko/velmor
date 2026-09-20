#!/usr/bin/env bash
set -euo pipefail

APP=/opt/velmor/app
ENVF="$APP/packages/api/.env.dev"

TOKEN="$(python3 - <<'PY'
import re
text = open("/tmp/create_app.out", encoding="utf-8").read()
match = re.search(r'"auth_token"\s*:\s*"([^"]+)"', text)
if not match:
    raise SystemExit("no auth_token in /tmp/create_app.out")
print(match.group(1))
PY
)"

DB="$(grep '^DATABASE_URL=' "$ENVF" | cut -d= -f2-)"
REDIS="$(grep '^REDIS_URL=' "$ENVF" | cut -d= -f2-)"
LOGFIRE="$(grep '^LOGFIRE_TOKEN=' "$ENVF" | cut -d= -f2-)"

umask 077
cat > "$ENVF" <<EOF
ENVIRONMENT=dev
DATABASE_URL=${DB}
REDIS_URL=${REDIS}
LOGFIRE_TOKEN=${LOGFIRE}
SALEOR_API_URL=http://127.0.0.1:8001/graphql/
SALEOR_APP_TOKEN=${TOKEN}
STRIPE_SECRET_KEY=sk_test_replace_me
STRIPE_WEBHOOK_SIGNING_SECRET=whsec_replace_me
BEPAID_SHOP_ID=test-bepaid-shop-id
BEPAID_SECRET_KEY=test-bepaid-secret-key
BEPAID_PUBLIC_KEY="-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtestplaceholderonly\nbootnotlivexxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\nxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\nxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\nxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx\nxwIDAQAB\n-----END PUBLIC KEY-----"
BEPAID_NOTIFICATION_URL=https://velmor-api.78-111-89-46.sslip.io/webhooks/bepaid
OPERATOR_REFUND_KEY=test-operator-refund-key
STOREFRONT_DOMAIN=shop.78-111-89-46.sslip.io
DELIVERY_GRANT_SECRET=test-delivery-grant-hmac-secret
DELIVERY_GRANT_LIFETIME_SECONDS=900
DELIVERY_CACHE_MAX_BYTES=268435456
DELIVERY_CACHE_DIR=var/delivery-cache
CATALOGUE_UNIT_AMOUNT=9.99
CATALOGUE_CURRENCY=BYN
EOF
chmod 600 "$ENVF"
echo "wrote commerce env keys:"
grep -E '^[A-Z_]+=' "$ENVF" | sed 's/=.*/=***/'

cd "$APP"
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
fi
uv sync

mkdir -p "$APP/var/delivery-cache"

systemctl restart velmor-api.service
sleep 5
systemctl is-active velmor-api.service
journalctl -u velmor-api -n 50 --no-pager
curl -s http://127.0.0.1:8080/health
echo
