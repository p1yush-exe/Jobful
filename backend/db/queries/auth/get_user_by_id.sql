select
  u.user_id,
  u.email,
  u.full_name,
  u.raw_job_title,
  u.bio,
  u.phone_number,
  u.github_url,
  u.linkedin_url,
  u.notion_url,
  u.email_verified_at,
  u.cv_uploaded,
  u.experience_years,
  u.created_at,
  u.updated_at,
  count(ust.tag_id) as selected_tags_count
from users u
left join user_selected_tags ust on ust.user_id = u.user_id
where u.user_id = %s
group by u.user_id;
