update refresh_sessions
set revoked_at = now(),
    revoke_reason = %s
where refresh_session_id = %s
  and revoked_at is null
returning refresh_session_id, user_id, current_jti, expires_at, revoked_at, revoke_reason, rotated_at, last_seen_at, created_at;
