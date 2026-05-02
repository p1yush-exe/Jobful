update jobs
set is_active = %s,
    stale_reason = %s,
    last_checked_at = now(),
    stale_detected_at = case
      when %s then null
      else coalesce(stale_detected_at, now())
    end
where job_id = %s
returning job_id, is_active, stale_reason, last_checked_at, stale_detected_at;
