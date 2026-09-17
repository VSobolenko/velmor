\echo '=== publishable records whose identity differs from what the source declared ==='
\echo '=== (a) how many are corroborated by a verified licence file from the page ==='
select
  case when exists (
         select 1 from jsonb_array_elements(r.record->'evidence') e
         where e.value->>'kind' = 'license_file')
       then 'with a verified licence file'
       else 'WITHOUT any licence file (uncorroborated)' end as corroboration,
  count(*)
from rights_records r
join candidates c on c.id = r.candidate_id
where r.publishable
  and c.declared_license_id is not null
  and c.declared_license_id is distinct from r.license_id
group by 1 order by 2 desc;

\echo ''
\echo '=== (b) the claim, the verified quote, and what the source said, for each ==='
select
  c.declared_license_id as source_said,
  r.license_id as published_as,
  coalesce((select e.value->>'excerpt' from jsonb_array_elements(r.record->'evidence') e
            where e.value->>'kind' = 'spdx_match' limit 1), '(none)') as matched_claim,
  coalesce((select left(e.value->>'excerpt', 60) from jsonb_array_elements(r.record->'evidence') e
            where e.value->>'kind' = 'license_file' limit 1), '(NO LICENCE FILE)') as verified_quote,
  count(*)
from rights_records r
join candidates c on c.id = r.candidate_id
where r.publishable
  and c.declared_license_id is not null
  and c.declared_license_id is distinct from r.license_id
group by 1, 2, 3, 4 order by 5 desc;

\echo ''
\echo '=== (c) the single uncorroborated case, in full ==='
select c.declared_license_id as source_said, r.license_id as published_as, jsonb_pretty(to_jsonb(r.record)) as record
from rights_records r
join candidates c on c.id = r.candidate_id
where r.publishable
  and c.declared_license_id is not null
  and c.declared_license_id is distinct from r.license_id
  and not exists (select 1 from jsonb_array_elements(r.record->'evidence') e
                  where e.value->>'kind' = 'license_file');
