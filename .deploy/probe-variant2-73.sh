#!/usr/bin/env bash
set -euo pipefail
TOKEN=$(grep '^SALEOR_APP_TOKEN=' /opt/velmor/app/packages/api/.env.dev | cut -d= -f2-)
PROD=UHJvZHVjdDox
curl -s -X POST http://127.0.0.1:8001/graphql/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d "{\"query\":\"mutation(\$i:ProductVariantCreateInput!){ productVariantCreate(input:\$i){ productVariant{id sku} errors{field message code} } }\",\"variables\":{\"i\":{\"product\":\"$PROD\",\"sku\":\"sku-openverse-ed3f4878-604d-4ee6-b3df-9dd969cb00e3\",\"attributes\":[]}}}" 
echo
