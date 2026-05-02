select distinct k.keyword
from keywords k
join experience_keywords ek on k.keyword_id = ek.keyword_id
join user_experiences e on ek.experience_id = e.experience_id
where e.user_id = %s;
