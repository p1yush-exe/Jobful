update users
set full_name = %s,
    raw_job_title = %s,
    bio = %s,
    phone_number = %s,
    github_url = %s,
    linkedin_url = %s,
    notion_url = %s,
    updated_at = now()
where user_id = %s
returning user_id;
