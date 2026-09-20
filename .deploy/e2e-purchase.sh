#!/usr/bin/env bash
# End-to-end stub purchase against the public Velmor API (task 7.4).
# Usage: STUB_WEBHOOK_SECRET=... .deploy/e2e-purchase.sh
# Never prints origin_url. Asserts DTO keys and known CDN host patterns absent.
set -euo pipefail

API="${API_BASE:-https://velmor-api.78-111-89-46.sslip.io}"
SHOP="${SHOP_BASE:-https://shop.78-111-89-46.sslip.io}"
BUYER="${BUYER_ID:-e2e-buyer}"
RETURN_URL="${RETURN_URL:-${SHOP}/return}"

if [[ -z "${STUB_WEBHOOK_SECRET:-}" ]]; then
  echo "STUB_WEBHOOK_SECRET is required" >&2
  exit 1
fi

FORBIDDEN_KEYS='origin_url content_digest download_url'
CDN_PATTERNS=(
  'upload.wikimedia.org'
  'live.staticflickr.com'
  'staticflickr.com'
  'i.creativecommons.org'
  'openverse.org'
  'api.openverse'
  'raw.githubusercontent.com'
  'images.openverse'
)

echo "=== shop homepage ==="
SHOP_HTML="$(curl -fsS "$SHOP/")"
echo "shop_http=200"
echo "$SHOP_HTML" | grep -qi 'Proofbasket\|approved for sale\|<title>' \
  && echo "shop_title_ok=yes" || { echo "shop_title_ok=no"; exit 1; }

echo "=== GET /checkout/providers ==="
PROVIDERS="$(curl -fsS "$API/checkout/providers")"
echo "providers=$PROVIDERS"
echo "$PROVIDERS" | grep -q '"stub"' || { echo "stub provider missing"; exit 1; }

echo "=== GET /catalogue/goods ==="
GOODS="$(curl -fsS "$API/catalogue/goods")"
CANDIDATE_ID="$(printf '%s' "$GOODS" | python3 -c 'import json,sys; g=json.load(sys.stdin); assert g; print(g[0]["candidate_id"])')"
UNIT_AMOUNT="$(printf '%s' "$GOODS" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["unit_amount"])')"
CURRENCY="$(printf '%s' "$GOODS" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["currency"])')"
echo "candidate_id=$CANDIDATE_ID"
echo "unit_amount=$UNIT_AMOUNT currency=$CURRENCY"

printf '%s' "$GOODS" | python3 -c '
import json, sys
forbidden = set(sys.argv[1].split())
goods = json.load(sys.stdin)
for item in goods[:5]:
    leak = [k for k in forbidden if k in item]
    if leak:
        raise SystemExit(f"forbidden keys in product DTO: {leak}")
print("product_dto_keys_ok=yes")
' "$FORBIDDEN_KEYS"

echo "=== GET /checkout/disclosure ==="
DISC="$(curl -fsS "$API/checkout/disclosure")"
printf '%s' "$DISC" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["complete"] is True, d; print("disclosure_complete=true")'

echo "=== POST /checkout/start (stub) ==="
START_BODY="$(python3 -c '
import json, os
print(json.dumps({
  "provider_id": "stub",
  "return_url": os.environ["RETURN_URL"],
  "currency": os.environ["CURRENCY"],
  "lines": [{
    "candidate_id": os.environ["CANDIDATE_ID"],
    "unit_amount": os.environ["UNIT_AMOUNT"],
    "quantity": 1,
  }],
}))
' )"
export RETURN_URL CANDIDATE_ID UNIT_AMOUNT CURRENCY
START="$(curl -fsS -X POST "$API/checkout/start" \
  -H "Content-Type: application/json" \
  -H "X-Buyer-Id: $BUYER" \
  -d "$START_BODY")"
ORDER_ID="$(printf '%s' "$START" | python3 -c 'import json,sys; b=json.load(sys.stdin); assert b["state"]=="pending", b; print(b["order_id"])')"
PROVIDER_REF="$(printf '%s' "$START" | python3 -c 'import json,sys; print(json.load(sys.stdin)["provider_reference"])')"
REDIRECT="$(printf '%s' "$START" | python3 -c 'import json,sys; print(json.load(sys.stdin)["redirect_url"])')"
echo "order_id=$ORDER_ID"
echo "state=pending"
echo "provider_reference=$PROVIDER_REF"
echo "redirect_url=$REDIRECT"

echo "=== POST /webhooks/stub ==="
export ORDER_ID PROVIDER_REF
PAYLOAD="$(python3 -c '
import json, os
print(json.dumps({
  "order_id": os.environ["ORDER_ID"],
  "amount": os.environ["UNIT_AMOUNT"],
  "currency": os.environ["CURRENCY"],
  "succeeded": True,
  "provider_reference": os.environ["PROVIDER_REF"],
}, separators=(",", ":")))
')"
SIGNATURE="$(printf '%s' "$PAYLOAD" | python3 -c '
import hashlib, hmac, os, sys
secret = os.environ["STUB_WEBHOOK_SECRET"].encode("utf-8")
payload = sys.stdin.buffer.read()
print(hmac.new(secret, payload, hashlib.sha256).hexdigest())
')"
WH="$(curl -fsS -X POST "$API/webhooks/stub" \
  -H "Content-Type: application/json" \
  -H "X-Stub-Signature: $SIGNATURE" \
  -d "$PAYLOAD")"
echo "webhook=$WH"

echo "=== GET /account/orders/{id} ==="
ORDER="$(curl -fsS "$API/account/orders/$ORDER_ID" -H "X-Buyer-Id: $BUYER")"
printf '%s' "$ORDER" | python3 -c 'import json,sys; o=json.load(sys.stdin); assert o["state"]=="paid", o; print("order_state=paid")'

echo "=== GET /account/entitlements ==="
ENTS="$(curl -fsS "$API/account/entitlements" -H "X-Buyer-Id: $BUYER")"
printf '%s' "$ENTS" | python3 -c '
import json, sys
candidate = sys.argv[1]
rows = json.load(sys.stdin)
active = [r for r in rows if r["candidate_id"] == candidate and r["state"] == "active"]
assert active, rows
print("entitlement_active=yes")
' "$CANDIDATE_ID"

download_once() {
  local label="$1"
  local grant token status bytes tmp
  grant="$(curl -fsS -X POST "$API/account/goods/$CANDIDATE_ID/grant" -H "X-Buyer-Id: $BUYER")"
  token="$(printf '%s' "$grant" | python3 -c 'import json,sys; print(json.load(sys.stdin)["token"])')"
  tmp="$(mktemp)"
  status="$(curl -sS -o "$tmp" -w '%{http_code}' \
    "$API/downloads/$token" -H "X-Buyer-Id: $BUYER")"
  bytes="$(wc -c < "$tmp" | tr -d ' ')"
  echo "${label}_status=$status bytes=$bytes"
  if [[ "$status" != "200" ]]; then rm -f "$tmp"; exit 1; fi
  if [[ "$bytes" -le 0 ]]; then rm -f "$tmp"; exit 1; fi
  for host in "${CDN_PATTERNS[@]}"; do
    if grep -a -F -q "$host" "$tmp"; then
      echo "concealment_fail=download_contains_$host"
      rm -f "$tmp"
      exit 1
    fi
  done
  rm -f "$tmp"
}

echo "=== download 1 ==="
download_once download1
echo "=== download 2 (re-grant) ==="
download_once download2

echo "=== concealment checks (API JSON + shop HTML) ==="
BLOB="$GOODS$DISC$START$ORDER$ENTS$SHOP_HTML$PROVIDERS"
for key in $FORBIDDEN_KEYS; do
  if printf '%s' "$BLOB" | grep -q "\"$key\""; then
    echo "concealment_fail=key_$key"
    exit 1
  fi
done
for host in "${CDN_PATTERNS[@]}"; do
  if printf '%s' "$BLOB" | grep -F -q "$host"; then
    echo "concealment_fail=host_$host"
    exit 1
  fi
done
echo "concealment_ok=yes"
echo "e2e_purchase_ok order_id=$ORDER_ID candidate_id=$CANDIDATE_ID"
