#!/usr/bin/env bash
set -uo pipefail

APP=/opt/velmor/app
DB='docker exec velmor-postgres psql -U velmor -d velmor -tAc'

sed -i 's|^AUDITOR_BATCH_SIZE=.*|AUDITOR_BATCH_SIZE=220|' "$APP/packages/auditor/.env.dev"

cd "$APP"
timeout 3000 ./.venv/bin/velmor run auditor --env dev 2>&1 | grep -E '^\[auditor\] run='

echo "publishable=$($DB 'select count(*) from rights_records where publishable')"
echo "decided=$($DB 'select count(*) from rights_records')"
echo "still_pending=$($DB 'select count(*) from candidates c left join rights_records r on r.candidate_id = c.id where r.candidate_id is null')"
echo "publishable_by_license:"
$DB 'select license_id, count(*) from rights_records where publishable group by 1 order by 2 desc'
echo done
