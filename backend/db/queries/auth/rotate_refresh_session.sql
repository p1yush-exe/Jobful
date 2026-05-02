update refresh_sessions
set current_jti = %s,
    expires_at = %s,
    rotated_at = now(),
    last_seen_at = now()
where refresh_session_id = %s
  and revoked_at is null
returning refresh_session_id, user_id, current_jti, expires_at, revoked_at, revoke_reason, rotated_at, last_seen_at, created_at;
