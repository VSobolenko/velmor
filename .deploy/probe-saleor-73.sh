#!/usr/bin/env bash
set -euo pipefail
echo "SALEOR_API_URL=$(grep '^SALEOR_API_URL=' /opt/velmor/app/packages/api/.env.dev | cut -d= -f2-)"
echo "token_len=$(grep '^SALEOR_APP_TOKEN=' /opt/velmor/app/packages/api/.env.dev | cut -d= -f2- | wc -c)"
curl -s -o /dev/null -w 'GET graphql/: %{http_code}\n' http://127.0.0.1:8001/graphql/
curl -s -o /tmp/gql1.json -w 'POST graphql/: %{http_code}\n' \
  -X POST http://127.0.0.1:8001/graphql/ \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ __typename shop { name } }"}'
cat /tmp/gql1.json; echo
TOKEN=$(grep '^SALEOR_APP_TOKEN=' /opt/velmor/app/packages/api/.env.dev | cut -d= -f2-)
curl -s -o /tmp/gql2.json -w 'POST auth productTypes: %{http_code}\n' \
  -X POST http://127.0.0.1:8001/graphql/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"query":"query { productTypes(first: 5) { edges { node { id name } } } }"}'
cat /tmp/gql2.json; echo
