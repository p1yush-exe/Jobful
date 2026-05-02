select
  e.experience_id,
  e.company,
  e.location,
  e.role,
  e.experience_type,
  e.start_date::text,
  e.end_date::text,
  e.description,
  ct.tag_name as tag,
  coalesce(
    array_agg(k.keyword order by k.keyword) filter (where k.keyword is not null),
    '{}'
  ) as keywords
from user_experiences e
left join canonical_tags ct on ct.tag_id = e.tag_id
left join experience_keywords ek on ek.experience_id = e.experience_id
left join keywords k on k.keyword_id = ek.keyword_id
where e.user_id = %s
group by e.experience_id, e.company, e.location, e.role, e.experience_type,
         e.start_date, e.end_date, e.description, ct.tag_name
order by e.start_date desc nulls last, e.created_at desc;
