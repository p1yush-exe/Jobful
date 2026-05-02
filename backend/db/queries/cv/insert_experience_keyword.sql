insert into experience_keywords (experience_id, keyword_id)
values (%s, %s)
on conflict do nothing;
