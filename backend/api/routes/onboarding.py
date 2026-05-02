from fastapi import APIRouter, Depends

from api.controllers.onboarding_controller import choose_tags, eligible_jobs, read_state, update_state
from api.dependencies.auth import get_current_user
from api.dependencies.common import get_db_connection
from api.schemas.onboarding import OnboardingStateResponse, ProfileUpdateRequest, SelectedTagsRequest
from db.executor import fetch_all
from db.query_loader import load_query

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.get("/state", response_model=OnboardingStateResponse)
def onboarding_state_route(current_user=Depends(get_current_user), connection=Depends(get_db_connection)):
    return read_state(connection, str(current_user["user_id"]))


@router.put("/profile", response_model=OnboardingStateResponse)
def onboarding_profile_route(payload: ProfileUpdateRequest, current_user=Depends(get_current_user), connection=Depends(get_db_connection)):
    return update_state(connection, str(current_user["user_id"]), payload)


@router.put("/selected-tags", response_model=OnboardingStateResponse)
def onboarding_selected_tags_route(payload: SelectedTagsRequest, current_user=Depends(get_current_user), connection=Depends(get_db_connection)):
    return choose_tags(connection, str(current_user["user_id"]), payload)


@router.get("/eligible-jobs")
def onboarding_eligible_jobs_route(current_user=Depends(get_current_user), connection=Depends(get_db_connection)):
    return {"items": eligible_jobs(connection, str(current_user["user_id"]))}


@router.get("/generate-tags")
def generate_tags_route(current_user=Depends(get_current_user), connection=Depends(get_db_connection)):
    """Returns distinct tags from the user's education, experiences, and projects — pure SQL, no AI."""
    user_id = str(current_user["user_id"])
    rows = fetch_all(connection, load_query("onboarding", "get_user_cv_tags.sql"), (user_id, user_id, user_id))
    return {"tags": [{"tag_id": str(r["tag_id"]), "tag_name": r["tag_name"]} for r in rows]}