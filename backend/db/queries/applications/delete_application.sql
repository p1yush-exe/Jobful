delete from applications
where application_id = %s and user_id = %s
returning application_id, job_id;
