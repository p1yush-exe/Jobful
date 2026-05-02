select
  a.application_id,
  a.user_id,
  a.job_id,
  a.status,
  a.applied_at,
  a.updated_at,
  j.title,
  j.company,
  j.location,
  j.salary_range,
  j.posted_at
from applications a
join jobs j on j.job_id = a.job_id
where a.user_id = %s
order by a.updated_at desc;
