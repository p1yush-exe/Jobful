insert into users (email, password_hash, full_name, raw_job_title, bio)
values (lower(%s), %s, %s, %s, %s)
returning user_id, email, full_name, raw_job_title, bio, email_verified_at, created_at, updated_at;
