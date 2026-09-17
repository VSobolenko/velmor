\echo '=== which evidence kinds appear in publishable records ==='
select e.value->>'kind' as kind, count(*) as records
from rights_records r, jsonb_array_elements(r.record->'evidence') e
where r.publishable
group by 1 order by 2 desc;

\echo ''
\echo '=== does any publishable record carry a verified licence-file quote? ==='
select count(*) as with_license_file
from rights_records r, jsonb_array_elements(r.record->'evidence') e
where r.publishable and e.value->>'kind' = 'license_file';

\echo ''
\echo '=== for publishable records: does the source API excerpt resolve to the published licence? ==='
select
  coalesce(e.value->>'excerpt', '(none)') as api_excerpt,
  r.license_id,
  count(*)
from rights_records r
left join lateral (
  select value from jsonb_array_elements(r.record->'evidence')
  where value->>'kind' = 'source_api_field' limit 1
) e on true
where r.publishable
group by 1, 2 order by 3 desc;

\echo ''
\echo '=== the 13 questionable records, in the scratch database ==='
select e.value->>'kind' as kind, count(*) as records
from (select record from rights_records r
      where r.publishable
        and r.candidate_id in (select candidate_id from refused_before)) r,
     jsonb_array_elements(r.record->'evidence') e
group by 1 order by 2 desc;
