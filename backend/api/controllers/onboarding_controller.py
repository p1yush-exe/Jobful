from api.schemas.onboarding import OnboardingStateResponse, ProfileUpdateRequest, SelectedTagsRequest
from services.onboarding_service import get_eligible_jobs, get_onboarding_state, set_selected_tags, update_profile_and_recommend_tags


def read_state(connection, user_id: str) -> OnboardingStateResponse:
    return get_onboarding_state(connection, user_id)


def update_state(connection, user_id: str, payload: ProfileUpdateRequest) -> OnboardingStateResponse:
    return update_profile_and_recommend_tags(connection, user_id, payload)


def choose_tags(connection, user_id: str, payload: SelectedTagsRequest) -> OnboardingStateResponse:
    return set_selected_tags(connection, user_id, payload)


def eligible_jobs(connection, user_id: str) -> list[dict[str, object]]:
    return get_eligible_jobs(connection, user_id)