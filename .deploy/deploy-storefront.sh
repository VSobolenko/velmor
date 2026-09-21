#!/usr/bin/env bash
# Deploy the storefront on the host: schema, dependencies, production build, restart.
#
# Run on the host after the checkout is at the intended commit:
#   bash /root/deploy-storefront.sh
#
# The API deliberately creates no schema of its own ("no schema to create" in
# velmor/api_server.py), so a new table reaches production only if something else
# creates it. That step was missing and the catalogue answered 500 with
# `relation "catalogue_presentations" does not exist` on the first deploy that
# added a table. `velmor cover list` is the no-token CLI path that opens the store
# through `_open_store`, which calls `ensure_schema` and is idempotent.
set -u

APP=/opt/velmor/app
cd "$APP" || exit 1
export PATH="$HOME/.local/bin:$PATH"

echo "=== commit under deploy ==="
git log --oneline -1

echo
echo '=== schema ==='
uv run velmor cover list --env dev 2>&1 | tail -2

echo
echo '=== storefront dependencies ==='
cd "$APP/storefront" || exit 1
# `npm ci` is reproducible only when package.json and the lock agree, and the lock
# must be installable by the npm on this host (9.2.0 here). A lock written by a newer
# npm omitted @emnapi/core and @emnapi/runtime, and `npm ci` refused to run at all.
npm ci --no-audit --no-fund > /tmp/npmci.log 2>&1
if [ $? -ne 0 ]; then
  echo 'npm ci failed:'
  tail -20 /tmp/npmci.log
  exit 1
fi
tail -2 /tmp/npmci.log

echo
echo '=== production build ==='
systemctl stop velmor-storefront.service
start=$(date +%s)
npm run build > /tmp/build.log 2>&1
code=$?
echo "build exit=$code in $(( $(date +%s) - start ))s"
if [ $code -ne 0 ]; then
  tail -30 /tmp/build.log
  exit 1
fi
tail -3 /tmp/build.log

echo
echo '=== restart ==='
systemctl start velmor-storefront.service
sleep 6
systemctl is-active velmor-storefront.service

echo
echo '=== verify through the public origin ==='
for path in / /en /ru /be /en/catalogue; do
  printf '%-16s ' "$path"
  curl -s -o /dev/null -w 'status=%{http_code} time=%{time_total}s\n' --max-time 30 "https://shop.78-111-89-46.sslip.io$path"
done

id=$(curl -s --max-time 25 'https://velmor-api.78-111-89-46.sslip.io/catalogue/goods?limit=1' | sed -n 's/.*"candidate_id":"\([^"]*\)".*/\1/p' | sed -n 1p)
printf 'product page     '
curl -s -o /dev/null -w 'status=%{http_code}\n' --max-time 30 "https://shop.78-111-89-46.sslip.io/en/goods/$id"
echo "DONE"
