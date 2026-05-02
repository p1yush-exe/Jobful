from api.schemas.cv import CVConfirmRequest, CVConfirmResponse, CVPreviewResponse
from services.cv_service import process_cv_upload, store_confirmed_cv_data


def upload_cv_preview(connection, user_id: str, file_bytes: bytes) -> CVPreviewResponse:
    result = process_cv_upload(connection, user_id, file_bytes)
    return CVPreviewResponse(**result)


def confirm_cv(connection, user_id: str, payload: CVConfirmRequest) -> CVConfirmResponse:
    result = store_confirmed_cv_data(connection, user_id, payload.model_dump())
    return CVConfirmResponse(**result)
