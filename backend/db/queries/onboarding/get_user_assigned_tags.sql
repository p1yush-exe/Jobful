select
  ct.tag_id,
  ct.tag_name
from user_assigned_tags uat
join canonical_tags ct on ct.tag_id = uat.tag_id
where uat.user_id = %s
order by ct.tag_name;
