#!/usr/bin/env bash
# Re-check the published shelf against the rule main now enforces, without touching
# a single production verdict.
#
# The runner only ever examines candidates that have no verdict, so a plain re-run
# would leave the existing shelf unexamined and prove nothing. Instead the candidates
# are copied into a scratch database with no verdicts and no checkpoints, and the
# auditor decides them there. Production rights_records is read at the end, never
# written.
#
# Only candidates and rights_records are copied. Copying the whole schema would drag
# the checkpoint tables along, and the graph would resume from a checkpoint left by a
# previous run instead of verifying the candidate from the start.
set -uo pipefail

APP=/opt/velmor/app
DB=velmor_recheck1
PG='docker exec velmor-postgres'

echo '=== create the scratch database ==='
$PG psql -q -U velmor -d postgres -c "CREATE DATABASE $DB OWNER velmor" 2>&1 | tail -3

echo
echo '=== copy the two tables Velmor owns ==='
$PG sh -c "pg_dump -U velmor -d velmor --schema-only --table=candidates --table=rights_records | psql -q -U velmor -d $DB" 2>&1 | tail -3
$PG sh -c "pg_dump -U velmor -d velmor --data-only --table=candidates | psql -q -U velmor -d $DB" 2>&1 | tail -3

echo
echo '=== scratch database holds (candidates / verdicts) ==='
$PG psql -U velmor -d $DB -tAc 'select count(*) from candidates'
$PG psql -U velmor -d $DB -tAc 'select count(*) from rights_records'

echo
echo '=== build the recheck profile ==='
umask 077
# Only the trailing database name changes, so the credentials stay exactly as the
# working dev profile has them.
sed -e 's|^ENVIRONMENT=.*|ENVIRONMENT=test|' \
    -e "s|\(^DATABASE_URL=.*\)/velmor$|\1/$DB|" \
    -e 's|^AUDITOR_BATCH_SIZE=.*|AUDITOR_BATCH_SIZE=250|' \
    "$APP/packages/auditor/.env.dev" > "$APP/packages/auditor/.env.test"
chmod 600 "$APP/packages/auditor/.env.test"

echo -n 'profile ENVIRONMENT: '; sed -n 's/^ENVIRONMENT=//p' "$APP/packages/auditor/.env.test"
echo -n 'profile database:    '; sed -n 's|^DATABASE_URL=.*@|...@|p' "$APP/packages/auditor/.env.test"
echo -n 'profile batch:       '; sed -n 's/^AUDITOR_BATCH_SIZE=//p' "$APP/packages/auditor/.env.test"

echo
echo '=== run the auditor against the scratch database ==='
cd "$APP"
timeout 2700 ./.venv/bin/velmor run auditor --env test 2>&1 | grep -E '^\[auditor\] run=' || echo 'RUN PRODUCED NO SUMMARY LINE'

echo
echo '===== WHAT CHANGED FOR THE PUBLISHED SHELF ====='
echo '--- production shelf, by licence ---'
$PG psql -U velmor -d velmor -c "select license_id, count(*) from rights_records where publishable group by 1 order by 2 desc"

echo '--- the same candidates, decided under the enforced rule ---'
$PG psql -U velmor -d $DB -c "
select coalesce(r.license_id, '(none)') as licence,
       r.verdict,
       r.publishable,
       count(*)
from rights_records r
where r.candidate_id in (select candidate_id from velmor.rights_records)
group by 1, 2, 3
order by 3 desc, 4 desc"

echo '--- how many of the published survive, how many do not ---'
$PG psql -U velmor -d $DB -tAc "
select concat('published before and now: ', count(*))
from rights_records
where publishable
  and candidate_id in (select candidate_id from velmor.rights_records where publishable)"

$PG psql -U velmor -d $DB -tAc "
select concat('published before, NOT now: ', count(*))
from rights_records
where not publishable
  and candidate_id in (select candidate_id from velmor.rights_records where publishable)"

$PG psql -U velmor -d $DB -tAc "
select concat('published before, still undecided now: ', count(*))
from velmor.rights_records p
where p.publishable
  and not exists (select 1 from rights_records r where r.candidate_id = p.candidate_id)"

echo '--- the ones that stopped being publishable, with reasons ---'
$PG psql -U velmor -d $DB -c "
select left(c.title, 45) as title, r.verdict, left(r.reason, 110) as reason
from rights_records r
join candidates c on c.id = r.candidate_id
where not r.publishable
  and r.candidate_id in (select candidate_id from velmor.rights_records where publishable)
order by c.title"

echo
echo '=== production shelf untouched ==='
$PG psql -U velmor -d velmor -tAc 'select count(*) from rights_records where publishable'
echo done
