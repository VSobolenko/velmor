#!/usr/bin/env bash
set -uo pipefail

APP=/opt/velmor/app
DB='docker exec velmor-postgres psql -U velmor -d velmor -tAc'

sed -i 's|^AUDITOR_BATCH_SIZE=.*|AUDITOR_BATCH_SIZE=40|' "$APP/packages/auditor/.env.dev"

cd "$APP"
for pass in 1 2 3 4 5; do
  echo "===== pass $pass ====="
  timeout 1200 ./.venv/bin/velmor run auditor --env dev 2>&1 | grep -E '^\[auditor\] run='
  echo "shelf=$($DB 'select count(*) from rights_records where publishable')"
done
echo '===== final ====='
echo "publishable=$($DB 'select count(*) from rights_records where publishable')"
echo "decided=$($DB 'select count(*) from rights_records')"
echo "candidates=$($DB 'select count(*) from candidates')"
