with ins as (
  insert into keywords (keyword)
  values (%s)
  on conflict (keyword) do nothing
  returning keyword_id
)
select keyword_id from ins
union all
select keyword_id from keywords where keyword = %s
limit 1;
