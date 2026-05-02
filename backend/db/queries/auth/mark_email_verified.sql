update users
set email_verified_at = now(),
    email_verification_code_hash = null,
    email_verification_code_salt = null,
    email_verification_expires_at = null,
    email_verification_sent_at = null,
    email_verification_attempts = 0,
    updated_at = now()
where user_id = %s
returning user_id, email, full_name, raw_job_title, bio, email_verified_at, created_at, updated_at;
