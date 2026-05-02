from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from api.controllers.cv_controller import confirm_cv, upload_cv_preview
from api.dependencies.auth import get_current_user
from api.dependencies.common import get_db_connection
from api.schemas.cv import CVConfirmRequest, CVConfirmResponse, CVPreviewResponse
from core.config import settings
from core.limiter import limiter


router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/upload-cv", response_model=CVPreviewResponse)
@limiter.limit("5/minute")
async def upload_cv_route(
    request: Request,
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
    connection=Depends(get_db_connection),
):
    """Parse CV → return preview for user review. Nothing written to DB."""
    if file.content_type not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only PDF files accepted")

    cap = settings.cv_max_bytes
    file_bytes = await file.read(cap + 1)
    if len(file_bytes) > cap:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"PDF exceeds {cap // (1024*1024)}MB limit")
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    if not file_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is not a valid PDF")

    return upload_cv_preview(connection, str(current_user["user_id"]), file_bytes)


@router.post("/confirm-cv", response_model=CVConfirmResponse)
@limiter.limit("10/minute")
def confirm_cv_route(
    request: Request,
    payload: CVConfirmRequest,
    current_user=Depends(get_current_user),
    connection=Depends(get_db_connection),
):
    """Write user-confirmed CV data to DB. Called after user reviews/edits the preview."""
    return confirm_cv(connection, str(current_user["user_id"]), payload)
