from db.executor import fetch_all
from db.query_loader import load_query


def list_eligible_jobs(connection, user_id: str) -> list[dict[str, object]]:
    return fetch_all(connection, load_query("jobs", "get_eligible_jobs.sql"), (user_id,))