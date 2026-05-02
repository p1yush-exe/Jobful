update users
set email_verification_code_hash = %s,
    email_verification_code_salt = %s,
    email_verification_expires_at = %s,
    email_verification_sent_at = now(),
    email_verification_attempts = 0,
    updated_at = now()
where user_id = %s
returning user_id, email, full_name, raw_job_title, bio, email_verified_at, email_verification_sent_at, email_verification_expires_at, email_verification_attempts;
