insert into user_experiences (
  user_id, company, location, role, experience_type,
  start_date, end_date, description, tag_id
)
values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
returning experience_id;
