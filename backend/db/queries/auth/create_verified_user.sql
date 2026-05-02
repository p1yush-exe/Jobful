insert into users (email, password_hash, full_name, raw_job_title, bio, email_verified_at)
values (%s, %s, %s, %s, %s, now())
returning user_id, email, full_name, raw_job_title, bio, phone_number, github_url, linkedin_url, notion_url, email_verified_at, created_at, updated_at;
