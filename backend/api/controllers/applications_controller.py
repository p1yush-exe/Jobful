from api.schemas.applications import (
    PrepareApplyResponse,
    RemoveApplicationResponse,
    TrackJobRequest,
    TrackJobResponse,
    UpdateStatusRequest,
)
from services.application_service import (
    get_applications_overview,
    list_user_applications,
    prepare_application_for_apply,
    remove_stale_interested_application,
    track_job,
    update_application_status,
)


def list_applications(connection, user_id: str):
    return {"items": list_user_applications(connection, user_id)}


def overview_applications(connection, user_id: str):
    return get_applications_overview(connection, user_id)


def track_job_controller(connection, user_id: str, payload: TrackJobRequest) -> TrackJobResponse:
    result = track_job(connection, user_id, payload.model_dump())
    return TrackJobResponse(**result)


def update_status_controller(connection, user_id: str, application_id: str, payload: UpdateStatusRequest):
    return update_application_status(connection, user_id, application_id, payload.status)


def prepare_apply_controller(connection, user_id: str, application_id: str) -> PrepareApplyResponse:
    result = prepare_application_for_apply(connection, user_id, application_id)
    return PrepareApplyResponse(**result)


def remove_application_controller(connection, user_id: str, application_id: str) -> RemoveApplicationResponse:
    result = remove_stale_interested_application(connection, user_id, application_id)
    return RemoveApplicationResponse(**result)
