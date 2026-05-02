insert into user_assigned_tags (user_id, tag_id)
values (%s, %s)
on conflict do nothing;
