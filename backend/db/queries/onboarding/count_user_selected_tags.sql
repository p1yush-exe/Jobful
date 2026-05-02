select count(*)::int as selected_count
from user_selected_tags
where user_id = %s;
