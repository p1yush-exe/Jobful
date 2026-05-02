select
  user_id,
  email,
  password_hash,
  full_name,
  raw_job_title,
  bio,
  phone_number,
  github_url,
  linkedin_url,
  notion_url,
  email_verified_at,
  created_at,
  updated_at
from users
where lower(email) = lower(%s)
limit 1;
