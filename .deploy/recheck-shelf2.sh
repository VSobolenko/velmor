#!/usr/bin/env bash
# Re-check the published shelf against the rule main now enforces, without touching
# production verdicts.
#
# The runner only examines candidates that have no verdict, so a plain re-run would
# leave the existing shelf unexamined and prove nothing. The candidates are copied
# into a scratch database that has no verdicts and no checkpoints, and the auditor
# decides them there.
#
# The profile is verified before the run starts. A previous attempt wrote a profile
# whose database name had silently not been substituted, and the run went to the
# production database instead; the guard below exists because of that.
set -uo pipefail

APP=/opt/velmor/app
DEV="$APP/packages/auditor/.env.dev"
TEST="$APP/packages/auditor/.env.test"
DB=velmor_recheck1
PG='docker exec velmor-postgres'

echo '=== build the recheck profile ==='
# The dev profile carries CRLF line endings, so the carriage return is stripped
# first: a trailing \r breaks the end anchor and the substitution silently no-ops.
umask 077
sed -e 's/\r$//' "$DEV" \
  | sed -e 's|^ENVIRONMENT=.*|ENVIRONMENT=test|' \
        -e "s|\(^DATABASE_URL=.*\)/velmor$|\1/$DB|" \
        -e 's|^AUDITOR_BATCH_SIZE=.*|AUDITOR_BATCH_SIZE=250|' \
  > "$TEST"
chmod 600 "$TEST"

echo -n 'profile ENVIRONMENT: '; sed -n 's/^ENVIRONMENT=//p' "$TEST"
echo -n 'profile database:    '; sed -n 's|^.*@|...@|p' "$TEST" | head -1
echo -n 'profile batch:       '; sed -n 's/^AUDITOR_BATCH_SIZE=//p' "$TEST"

# Refuse to run unless the profile really addresses the scratch database.
if ! grep -q "^DATABASE_URL=.*/$DB$" "$TEST"; then
  echo 'REFUSING TO RUN: the profile does not address the scratch database.'
  exit 1
fi
echo 'guard passed: the profile addresses the scratch database'

echo
echo '=== record the published shelf inside the scratch database ==='
# PostgreSQL cannot join across databases, so the shelf is copied in as a table.
$PG psql -q -U velmor -d "$DB" -c 'drop table if exists shelf' 2>&1 | tail -2
$PG psql -q -U velmor -d "$DB" -c 'create table shelf(candidate_id text primary key)' 2>&1 | tail -2
$PG sh -c "psql -U velmor -d velmor -tAc 'select candidate_id from rights_records where publishable' | psql -q -U velmor -d $DB -c 'copy shelf(candidate_id) from stdin'" 2>&1 | tail -2
echo -n 'shelf rows recorded: '; $PG psql -U velmor -d "$DB" -tAc 'select count(*) from shelf'
echo -n 'candidates in scratch: '; $PG psql -U velmor -d "$DB" -tAc 'select count(*) from candidates'
echo -n 'verdicts in scratch: '; $PG psql -U velmor -d "$DB" -tAc 'select count(*) from rights_records'

echo
echo '=== run the auditor against the scratch database ==='
cd "$APP"
timeout 2700 ./.venv/bin/velmor run auditor --env test 2>&1 | tail -25

echo
echo '===== RESULT ====='
echo '--- production shelf (unchanged, for reference) ---'
$PG psql -U velmor -d velmor -c "select license_id, count(*) from rights_records where publishable group by 1 order by 2 desc"

echo '--- the same candidates, decided under the enforced rule ---'
$PG psql -U velmor -d "$DB" -c "
select coalesce(r.license_id, '(none)') as licence, r.verdict, r.publishable, count(*)
from rights_records r
where r.candidate_id in (select candidate_id from shelf)
group by 1, 2, 3
order by 3 desc, 4 desc"

echo '--- tally ---'
$PG psql -U velmor -d "$DB" -tAc "
select concat('published before AND now:      ', count(*))
from shelf s
join rights_records r on r.candidate_id = s.candidate_id
where r.publishable"

$PG psql -U velmor -d "$DB" -tAc "
select concat('published before, refused now: ', count(*))
from shelf s
join rights_records r on r.candidate_id = s.candidate_id
where not r.publishable"

$PG psql -U velmor -d "$DB" -tAc "
select concat('published before, paused now:  ', count(*))
from shelf s
where not exists (select 1 from rights_records r where r.candidate_id = s.candidate_id)"

echo '--- the ones that stopped being publishable, with reasons ---'
$PG psql -U velmor -d "$DB" -c "
select left(c.title, 38) as title, r.verdict, left(r.reason, 95) as reason
from shelf s
join rights_records r on r.candidate_id = s.candidate_id
join candidates c on c.id = r.candidate_id
where not r.publishable
order by c.title"

echo '--- the whole scratch run, by licence ---'
$PG psql -U velmor -d "$DB" -c "
select coalesce(license_id, '(none)') as licence, verdict, publishable, count(*)
from rights_records
group by 1, 2, 3
order by 3 desc, 4 desc"

echo
echo '=== production verdicts are still untouched ==='
$PG psql -U velmor -d velmor -tAc "select concat('decided=', count(*)) from rights_records"
$PG psql -U velmor -d velmor -tAc "select concat('publishable=', count(*)) from rights_records where publishable"
echo done
