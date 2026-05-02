select distinct k.keyword
from keywords k
join project_keywords pk on k.keyword_id = pk.keyword_id
join user_projects p on pk.project_id = p.project_id
where p.user_id = %s;
