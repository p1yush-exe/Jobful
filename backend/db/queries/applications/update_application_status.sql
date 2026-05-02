update applications
set status = %s, updated_at = now()
where application_id = %s and user_id = %s
returning application_id, status;
