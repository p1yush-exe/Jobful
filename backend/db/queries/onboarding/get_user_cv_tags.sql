select distinct ct.tag_id, ct.tag_name
from canonical_tags ct
where ct.tag_id in (
  select tag_id from user_education   where user_id = %s
  union
  select tag_id from user_experiences where user_id = %s and tag_id is not null
  union
  select tag_id from user_projects    where user_id = %s and tag_id is not null
)
order by ct.tag_name;
