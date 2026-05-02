select distinct
  j.job_id,
  j.title,
  j.company,
  j.location,
  j.salary_range,
  j.posted_at
from jobs j
join job_tags jt on jt.job_id = j.job_id
join user_selected_tags ust on ust.tag_id = jt.tag_id
where ust.user_id = %s
order by j.posted_at desc;
