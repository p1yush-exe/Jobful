select
  a.application_id,
  a.user_id,
  a.job_id,
  a.status,
  a.applied_at,
  a.updated_at,
  js.source_name as job_source,
  j.external_job_key,
  j.title,
  j.company,
  j.description,
  j.location,
  j.salary_range,
  j.apply_url,
  j.source_url,
  j.is_active,
  j.stale_reason,
  j.last_checked_at,
  j.stale_detected_at,
  j.posted_at
from applications a
join jobs j on j.job_id = a.job_id
left join job_sources js on js.source_id = j.source_id
where a.user_id = %s
order by a.updated_at desc;
