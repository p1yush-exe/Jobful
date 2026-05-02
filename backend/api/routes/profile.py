from fastapi import APIRouter, Depends

from api.dependencies.auth import get_current_user
from api.dependencies.common import get_db_connection
from api.schemas.auth import UserResponse
from api.schemas.profile import ProfileAccountUpdateRequest
from db.executor import fetch_all
from db.query_loader import load_query
from services.profile_service import update_profile_account

router = APIRouter(prefix="/profile", tags=["profile"])


@router.put("/account", response_model=UserResponse)
def update_account(payload: ProfileAccountUpdateRequest, current_user=Depends(get_current_user), connection=Depends(get_db_connection)):
    user_id = str(current_user["user_id"])
    return update_profile_account(connection, user_id, payload)


@router.get("/cv-data")
def get_cv_data(current_user=Depends(get_current_user), connection=Depends(get_db_connection)):
    user_id = str(current_user["user_id"])

    edu_rows = fetch_all(connection, load_query("cv", "get_user_education.sql"), (user_id,))
    exp_rows = fetch_all(connection, load_query("cv", "get_user_experiences_detail.sql"), (user_id,))
    proj_rows = fetch_all(connection, load_query("cv", "get_user_projects_detail.sql"), (user_id,))

    def _serialize(row):
        out = dict(row)
        for key in ("education_id", "experience_id", "project_id"):
            if key in out and out[key] is not None:
                out[key] = str(out[key])
        for key in ("start_date", "end_date"):
            if key in out and out[key] is not None and not isinstance(out[key], str):
                out[key] = str(out[key])
        return out

    return {
        "education": [_serialize(r) for r in edu_rows],
        "experiences": [_serialize(r) for r in exp_rows],
        "projects": [_serialize(r) for r in proj_rows],
    }


@router.get("/stats")
def get_stats(current_user=Depends(get_current_user), connection=Depends(get_db_connection)):
    user_id = str(current_user["user_id"])
    tag_stats = fetch_all(connection, load_query("applications", "get_applications_per_tag.sql"), (user_id,))
    return {"tag_stats": [dict(r) for r in tag_stats]}
