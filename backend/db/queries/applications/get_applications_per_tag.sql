select
  ct.tag_name,
  count(a.application_id) as application_count
from user_selected_tags ust
join canonical_tags ct on ct.tag_id = ust.tag_id
left join job_tags jt on jt.tag_id = ust.tag_id
left join applications a on a.job_id = jt.job_id and a.user_id = ust.user_id
where ust.user_id = %s
group by ct.tag_name
order by application_count desc, ct.tag_name;
