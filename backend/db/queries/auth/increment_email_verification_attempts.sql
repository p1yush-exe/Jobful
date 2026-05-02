update users
set email_verification_attempts = email_verification_attempts + 1,
    updated_at = now()
where user_id = %s
returning email_verification_attempts;
