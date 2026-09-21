#!/usr/bin/env bash
set -euo pipefail

APP=/opt/velmor/app
cd "$APP"
export PATH="$HOME/.local/bin:$PATH"

psql_velmor() {
  docker exec -i velmor-postgres psql -U velmor -d velmor "$@"
}

echo "=== env keys (names only) ==="
grep -E '^(SALEOR_API_URL|DATABASE_URL|DELIVERY_CACHE_DIR|SALEOR_APP_TOKEN)=' packages/api/.env.dev \
  | sed 's/=.*/=***/'

echo "=== saleor ==="
curl -s -o /dev/null -w 'saleor-health:%{http_code}\n' http://127.0.0.1:8001/health/
mkdir -p "$APP/var/delivery-cache"

echo "=== published_count before ==="
PUBLISHABLE=$(psql_velmor -tAc "SELECT count(*) FROM rights_records WHERE publishable IS TRUE;")
echo "gate_publishable=$PUBLISHABLE"

echo "=== velmor publish --env dev ==="
set +e
uv run velmor publish --env dev 2>&1 | tee /tmp/velmor-publish-73.log
PUBLISH_RC=${PIPESTATUS[0]}
set -e
echo "=== publish exit: $PUBLISH_RC ==="
echo "=== summary tail ==="
tail -40 /tmp/velmor-publish-73.log

echo "=== restart velmor-api ==="
systemctl restart velmor-api.service
sleep 4
systemctl is-active velmor-api.service

echo "=== catalogue SQL ==="
psql_velmor -c "SELECT state, listing, count(*) FROM catalogue_entries GROUP BY 1, 2 ORDER BY 1, 2;"
psql_velmor -c "
SELECT
  count(*) FILTER (WHERE state = 'published') AS published,
  count(*) FILTER (WHERE state = 'withdrawn') AS withdrawn,
  count(*) FILTER (WHERE listing = 'free_only') AS free_only,
  count(*) FILTER (WHERE category_id IS NULL) AS no_category,
  count(*) AS total
FROM catalogue_entries;
"
psql_velmor -c "SELECT count(*) AS categories FROM categories;"

# License families among gate-publishable goods
echo "=== license_id among publishable ==="
psql_velmor -c "
SELECT record->>'license_id' AS license_id, count(*)
FROM rights_records
WHERE publishable IS TRUE
GROUP BY 1
ORDER BY 2 DESC;
"

echo "=== API /catalogue/goods sample ==="
curl -s http://127.0.0.1:8080/catalogue/goods > /tmp/catalogue-goods.json
python3 - <<'PY'
import json
with open('/tmp/catalogue-goods.json', encoding='utf-8') as f:
    data = json.load(f)
goods = data if isinstance(data, list) else data.get('goods', [])
print('type', type(data).__name__)
if isinstance(data, dict):
    print('keys', sorted(data.keys()))
print('count', len(goods) if isinstance(goods, list) else 'n/a')
if isinstance(goods, list):
    for g in goods[:5]:
        print(f"  {g.get('candidate_id')} listing={g.get('listing')} title={g.get('title')!r}")
    free = [g for g in goods if g.get('listing') == 'free_only']
    print('free_only_in_api', len(free))
PY

echo "=== public API ==="
curl -s -o /dev/null -w 'public-goods:%{http_code}\n' https://velmor-api.78-111-89-46.sslip.io/catalogue/goods
curl -s https://velmor-api.78-111-89-46.sslip.io/catalogue/goods > /tmp/public-goods.json
python3 -c "import json; d=json.load(open('/tmp/public-goods.json')); g=d if isinstance(d,list) else d.get('goods',[]); print('public_count', len(g) if isinstance(g,list) else d)"

echo "=== shop page ==="
curl -s -o /dev/null -w 'shop:%{http_code}\n' https://shop.78-111-89-46.sslip.io/

# Action counts from log
echo "=== action counts from log ==="
python3 - <<'PY'
from collections import Counter
counts = Counter()
for line in open('/tmp/velmor-publish-73.log', encoding='utf-8', errors='replace'):
    first = line.split(None, 1)[0] if line.strip() else ''
    if first in {'published', 'updated', 'withdrawn', 'refused', 'unchanged'}:
        counts[first] += 1
    if line.startswith('processed ') or line.startswith('  '):
        print(line.rstrip())
print('parsed', dict(counts))
PY

exit "$PUBLISH_RC"
