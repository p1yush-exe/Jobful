select
  u.user_id,
  u.email,
  u.full_name,
  u.email_verified_at,
  u.email_verification_code_hash,
  u.email_verification_code_salt,
  u.email_verification_expires_at,
  u.email_verification_sent_at,
  u.email_verification_attempts
from users u
where lower(u.email) = lower(%s)
limit 1;
