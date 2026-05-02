create or replace view application_summary
with (security_invoker = true)
as
select
  a.application_id,
  a.user_id,
  u.full_name as user_full_name,
  u.email as user_email,
  a.job_id,
  j.title as job_title,
  j.company,
  j.location,
  j.salary_range,
  j.source_url,
  j.external_job_key,
  j.posted_at,
  a.status,
  a.applied_at,
  a.updated_at
from applications a
join users u on u.user_id = a.user_id
join jobs j on j.job_id = a.job_id;

alter view application_summary set (security_invoker = true);
