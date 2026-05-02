insert into project_keywords (project_id, keyword_id)
values (%s, %s)
on conflict do nothing;
