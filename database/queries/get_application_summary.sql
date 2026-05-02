select
  application_id,
  user_id,
  user_full_name,
  user_email,
  job_id,
  job_title,
  company,
  location,
  salary_range,
  source_url,
  external_job_key,
  posted_at,
  status,
  applied_at,
  updated_at
from application_summary
order by applied_at desc;
