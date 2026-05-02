select
  ct.tag_id,
  ct.tag_name
from user_selected_tags ust
join canonical_tags ct on ct.tag_id = ust.tag_id
where ust.user_id = %s
order by ct.tag_name;
