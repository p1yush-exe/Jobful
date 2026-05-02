insert into user_projects (user_id, name, description, tag_id)
values (%s, %s, %s, %s)
returning project_id;
