delete from jobs j
where j.job_id = %s
  and not exists (
    select 1
    from applications a
    where a.job_id = j.job_id
  )
  and not exists (
    select 1
    from generated_documents gd
    where gd.job_id = j.job_id
  )
returning j.job_id;
