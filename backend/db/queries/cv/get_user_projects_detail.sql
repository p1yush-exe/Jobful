select
  p.project_id,
  p.name,
  p.description,
  ct.tag_name as tag,
  coalesce(
    array_agg(k.keyword order by k.keyword) filter (where k.keyword is not null),
    '{}'
  ) as keywords
from user_projects p
left join canonical_tags ct on ct.tag_id = p.tag_id
left join project_keywords pk on pk.project_id = p.project_id
left join keywords k on k.keyword_id = pk.keyword_id
where p.user_id = %s
group by p.project_id, p.name, p.description, ct.tag_name
order by p.created_at desc;
