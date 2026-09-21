#!/usr/bin/env bash
set -euo pipefail
cd /opt/velmor/app
git fetch /root/velmor-73b.bundle feat/add-storefront-commerce:refs/heads/deploy-73b
git checkout deploy-73b -- .
git log -1 --oneline deploy-73b
# smoke: Saleor with token
TOKEN=$(grep '^SALEOR_APP_TOKEN=' packages/api/.env.dev | cut -d= -f2-)
curl -s -o /tmp/gql-smoke.json -w 'gql:%{http_code}\n' \
  -X POST http://127.0.0.1:8001/graphql/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{"query":"{ shop { name } }"}'
head -c 200 /tmp/gql-smoke.json; echo
sed -i 's/\r$//' /tmp/run-publish-73.sh
chmod +x /tmp/run-publish-73.sh
nohup /tmp/run-publish-73.sh > /tmp/run-publish-73.out 2>&1 &
echo "started PID=$!"
