\echo '=== the 13 that went from refused to publishable: what did they resolve to? ==='
select coalesce(r.license_id, '(none)') as resolved_to, r.verdict, count(*)
from refused_before p
join rights_records r on r.candidate_id = p.candidate_id
where r.publishable
group by 1, 2 order by 3 desc;

\echo ''
\echo '=== and what the source had declared for them ==='
select c.declared_license_id, coalesce(r.license_id, '(none)') as resolved_to, count(*)
from refused_before p
join rights_records r on r.candidate_id = p.candidate_id
join candidates c on c.id = r.candidate_id
where r.publishable
group by 1, 2 order by 3 desc;

\echo ''
\echo '=== one full record, to see the evidence that carried it ==='
select jsonb_pretty(to_jsonb(r.record)) as record
from refused_before p
join rights_records r on r.candidate_id = p.candidate_id
where r.publishable
limit 1;

\echo ''
\echo '=== the 11 that now pause instead of being refused ==='
select c.declared_license_id, count(*)
from refused_before p
join candidates c on c.id = p.candidate_id
where not exists (select 1 from rights_records r where r.candidate_id = p.candidate_id)
group by 1 order by 2 desc;

\echo ''
\echo '=== are the paused ones out of investigation attempts, or waiting? ==='
select left(p.reason, 60) as refused_before, count(*)
from refused_before p
where not exists (select 1 from rights_records r where r.candidate_id = p.candidate_id)
group by 1 order by 2 desc;
