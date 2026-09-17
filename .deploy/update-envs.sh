#!/usr/bin/env bash
set -euo pipefail

APP=/opt/velmor/app
QUERIES='cc0, public domain, public domain art, public domain photograph, cc0 photograph, vintage photograph, old painting, public domain illustration, public domain book cover, public domain map, botanical illustration, museum photograph'

sed -i "s|^SCOUT_QUERIES=.*|SCOUT_QUERIES=${QUERIES}|" "$APP/packages/scout/.env.dev"
sed -i 's|^SCOUT_PAGE_LIMIT=.*|SCOUT_PAGE_LIMIT=20|' "$APP/packages/scout/.env.dev"
sed -i 's|^AUDITOR_BATCH_SIZE=.*|AUDITOR_BATCH_SIZE=25|' "$APP/packages/auditor/.env.dev"

grep -E 'SCOUT_QUERIES|SCOUT_PAGE_LIMIT' "$APP/packages/scout/.env.dev"
grep -E 'AUDITOR_BATCH_SIZE' "$APP/packages/auditor/.env.dev"
