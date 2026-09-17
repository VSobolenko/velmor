#!/usr/bin/env bash
# Compare what the old code refused in production with what the new rule does with
# the same candidates. Production is read only; nothing is written to it.
set -uo pipefail

PG='docker exec velmor-postgres'
DB=velmor_recheck1

echo '=== copy production refusals into the scratch database ==='
$PG psql -q -U velmor -d "$DB" -c 'drop table if exists refused_before' 2>&1 | tail -1
$PG psql -q -U velmor -d "$DB" -c 'create table refused_before(candidate_id text primary key, reason text)' 2>&1 | tail -1
$PG sh -c "psql -U velmor -d velmor -tAc \"select candidate_id || E'\\t' || replace(reason, E'\\n', ' ') from rights_records where not publishable\" | psql -q -U velmor -d $DB -c 'copy refused_before(candidate_id, reason) from stdin'" 2>&1 | tail -1
echo -n 'refusals copied: '; $PG psql -U velmor -d "$DB" -tAc 'select count(*) from refused_before'

echo
echo '=== 1. what production refused, and why ==='
$PG psql -U velmor -d "$DB" -c "
select left(p.reason, 75) as reason, count(*)
from refused_before p group by 1 order by 2 desc"

echo '=== 2. those same candidates under the new rule ==='
$PG psql -U velmor -d "$DB" -c "
select
  case
    when r.candidate_id is null then 'no verdict (paused for a human)'
    when r.publishable then 'publishable now'
    else concat('still refused: ', left(r.reason, 50))
  end as under_new_rule,
  count(*)
from refused_before p
left join rights_records r on r.candidate_id = p.candidate_id
group by 1 order by 2 desc"

echo '=== 3. the scratch run in full ==='
$PG psql -U velmor -d "$DB" -tAc "select concat('candidates:      ', count(*)) from candidates"
$PG psql -U velmor -d "$DB" -tAc "select concat('decided:         ', count(*)) from rights_records"
$PG psql -U velmor -d "$DB" -tAc "select concat('paused (no row): ', count(*)) from candidates c where not exists (select 1 from rights_records r where r.candidate_id = c.id)"

echo
echo '=== 4. the headline: the 105 published goods under the new rule ==='
$PG psql -U velmor -d "$DB" -c "
select r.publishable, count(*)
from shelf s join rights_records r on r.candidate_id = s.candidate_id
group by 1"

echo '=== 5. production is still untouched ==='
$PG psql -U velmor -d velmor -tAc "select concat('decided=', count(*)) from rights_records"
$PG psql -U velmor -d velmor -tAc "select concat('publishable=', count(*)) from rights_records where publishable"
echo done
