select
  e.education_id,
  e.institution,
  e.degree,
  e.degree_level,
  e.field_of_study,
  e.start_date::text,
  e.end_date::text,
  e.grade,
  e.description,
  ct.tag_name as tag
from user_education e
join canonical_tags ct on ct.tag_id = e.tag_id
where e.user_id = %s
order by e.end_date desc nulls first, e.start_date desc nulls last;
