update users
set raw_job_title = %s,
    bio = %s,
    updated_at = now()
where user_id = %s
returning user_id, email, full_name, raw_job_title, bio, phone_number, github_url, linkedin_url, notion_url, created_at, updated_at;
