from fastapi import HTTPException, status

from api.schemas.profile import ProfileAccountUpdateRequest
from core.security import hash_password
from db.executor import fetch_one, fetch_one_commit
from db.query_loader import load_query


def update_profile_account(connection, user_id: str, payload: ProfileAccountUpdateRequest) -> dict[str, object]:
    if payload.password:
        fetch_one_commit(
            connection,
            load_query("auth", "update_user_full_name_password.sql"),
            (
                payload.full_name,
                payload.raw_job_title,
                payload.bio,
                payload.phone_number,
                payload.github_url,
                payload.linkedin_url,
                payload.notion_url,
                hash_password(payload.password),
                user_id,
            ),
        )
    else:
        fetch_one_commit(
            connection,
            load_query("auth", "update_user_full_name.sql"),
            (
                payload.full_name,
                payload.raw_job_title,
                payload.bio,
                payload.phone_number,
                payload.github_url,
                payload.linkedin_url,
                payload.notion_url,
                user_id,
            ),
        )

    user = fetch_one(connection, load_query("auth", "get_user_by_id.sql"), (user_id,))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user["selected_tags_count"] = int(user.get("selected_tags_count", 0))
    user["onboarding_complete"] = bool(user.get("raw_job_title")) and user["selected_tags_count"] > 0
    user["cv_uploaded"] = bool(user.get("cv_uploaded", False))
    return user
