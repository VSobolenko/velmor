#!/usr/bin/env bash
set -euo pipefail
echo "=== refused ==="
grep '^refused' /tmp/velmor-publish-73.log || true
echo "=== run-publish tail ==="
tail -50 /tmp/run-publish-73.out
echo "=== local API ==="
curl -s http://127.0.0.1:8080/catalogue/goods > /tmp/catalogue-goods.json
python3 <<'PY'
import json
g=json.load(open('/tmp/catalogue-goods.json'))
print('count', len(g))
for x in g[:5]:
    print(x.get('candidate_id'), x.get('listing'), repr(x.get('title'))[:80])
print('free_only', sum(1 for x in g if x.get('listing')=='free_only'))
print('paid_ok', sum(1 for x in g if x.get('listing')=='paid_ok'))
PY
echo "=== public ==="
curl -s -o /dev/null -w 'public-goods:%{http_code}\n' https://velmor-api.78-111-89-46.sslip.io/catalogue/goods
curl -s https://velmor-api.78-111-89-46.sslip.io/catalogue/goods > /tmp/public-goods.json
python3 -c "import json; print('public_count', len(json.load(open('/tmp/public-goods.json'))))"
curl -s -o /dev/null -w 'shop:%{http_code}\n' https://shop.78-111-89-46.sslip.io/
