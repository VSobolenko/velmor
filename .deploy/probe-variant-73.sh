#!/usr/bin/env bash
set -euo pipefail
TOKEN=$(grep '^SALEOR_APP_TOKEN=' /opt/velmor/app/packages/api/.env.dev | cut -d= -f2-)
# Find any existing product or create a product type + product
curl -s -X POST http://127.0.0.1:8001/graphql/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"query":"query { productTypes(first:5){ edges{ node{ id name }}}}"}' > /tmp/pt.json
python3 - <<'PY'
import json
d=json.load(open('/tmp/pt.json'))
print(json.dumps(d, indent=2)[:1500])
PY

# Try productVariantCreate with minimal input against first product if any
curl -s -X POST http://127.0.0.1:8001/graphql/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"query":"query { products(first:3){ edges{ node{ id name slug variants{ id sku }}}} }"}' > /tmp/prods.json
python3 - <<'PY'
import json
d=json.load(open('/tmp/prods.json'))
print(json.dumps(d, indent=2)[:2000])
PY

# If we have a product, try create variant with colon sku
PROD=$(python3 -c "import json;d=json.load(open('/tmp/prods.json'));e=d.get('data',{}).get('products',{}).get('edges',[]);print(e[0]['node']['id'] if e else '')")
if [[ -n "$PROD" ]]; then
  echo "PROD=$PROD"
  curl -s -X POST http://127.0.0.1:8001/graphql/ \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${TOKEN}" \
    -d "{\"query\":\"mutation(\$i:ProductVariantCreateInput!){ productVariantCreate(input:\$i){ productVariant{id sku} errors{field message code} } }\",\"variables\":{\"i\":{\"product\":\"$PROD\",\"sku\":\"sku-openverse:test-1\"}}}" > /tmp/var1.json
  echo "colon sku:"; cat /tmp/var1.json; echo
  curl -s -X POST http://127.0.0.1:8001/graphql/ \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${TOKEN}" \
    -d "{\"query\":\"mutation(\$i:ProductVariantCreateInput!){ productVariantCreate(input:\$i){ productVariant{id sku} errors{field message code} } }\",\"variables\":{\"i\":{\"product\":\"$PROD\",\"sku\":\"sku-openverse-test-1\"}}}" > /tmp/var2.json
  echo "safe sku:"; cat /tmp/var2.json; echo
fi
