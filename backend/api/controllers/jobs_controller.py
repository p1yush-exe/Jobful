from services.job_service import list_eligible_jobs


def list_jobs(connection, user_id: str) -> list[dict[str, object]]:
    return list_eligible_jobs(connection, user_id)