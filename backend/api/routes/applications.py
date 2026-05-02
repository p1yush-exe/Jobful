from fastapi import APIRouter, Depends, Response

from api.controllers.applications_controller import (
    application_detail_controller,
    application_documents_controller,
    compile_document_controller,
    generate_document_controller,
    list_applications,
    overview_applications,
    prepare_apply_controller,
    remove_application_controller,
    track_job_controller,
    update_status_controller,
)
from api.dependencies.auth import get_current_user
from api.dependencies.common import get_db_connection
from api.schemas.applications import (
    ApplicationDetailResponse,
    ApplicationDocumentResponse,
    ApplicationsOverviewResponse,
    CompileDocumentRequest,
    GenerateDocumentRequest,
    PrepareApplyResponse,
    RemoveApplicationResponse,
    TrackJobRequest,
    TrackJobResponse,
    UpdateStatusRequest,
)

router = APIRouter(tags=["applications"])


@router.get("/applications")
def applications_route(current_user=Depends(get_current_user), connection=Depends(get_db_connection)):
    return list_applications(connection, str(current_user["user_id"]))


@router.get("/applications/overview", response_model=ApplicationsOverviewResponse)
def applications_overview_route(current_user=Depends(get_current_user), connection=Depends(get_db_connection)):
    return overview_applications(connection, str(current_user["user_id"]))


@router.get("/applications/{application_id}", response_model=ApplicationDetailResponse)
def application_detail_route(
    application_id: str,
    current_user=Depends(get_current_user),
    connection=Depends(get_db_connection),
):
    return application_detail_controller(connection, str(current_user["user_id"]), application_id)


@router.post("/applications/track", response_model=TrackJobResponse)
def track_job_route(
    payload: TrackJobRequest,
    current_user=Depends(get_current_user),
    connection=Depends(get_db_connection),
):
    return track_job_controller(connection, str(current_user["user_id"]), payload)


@router.put("/applications/{application_id}/status")
def update_status_route(
    application_id: str,
    payload: UpdateStatusRequest,
    current_user=Depends(get_current_user),
    connection=Depends(get_db_connection),
):
    return update_status_controller(connection, str(current_user["user_id"]), application_id, payload)


@router.post("/applications/{application_id}/prepare-apply", response_model=PrepareApplyResponse)
def prepare_apply_route(
    application_id: str,
    current_user=Depends(get_current_user),
    connection=Depends(get_db_connection),
):
    return prepare_apply_controller(connection, str(current_user["user_id"]), application_id)


@router.get("/applications/{application_id}/documents")
def application_documents_route(
    application_id: str,
    current_user=Depends(get_current_user),
    connection=Depends(get_db_connection),
):
    return application_documents_controller(connection, str(current_user["user_id"]), application_id)


@router.post("/applications/{application_id}/documents/generate")
def generate_document_route(
    application_id: str,
    payload: GenerateDocumentRequest,
    current_user=Depends(get_current_user),
    connection=Depends(get_db_connection),
):
    return generate_document_controller(connection, str(current_user["user_id"]), application_id, payload)


@router.post("/applications/{application_id}/documents/compile")
async def compile_document_route(
    application_id: str,
    payload: CompileDocumentRequest,
    current_user=Depends(get_current_user),
    connection=Depends(get_db_connection),
):
    result = await compile_document_controller(connection, str(current_user["user_id"]), application_id, payload)
    pdf_bytes = result.pop("pdf_bytes")
    filename = f"{payload.document_type.replace('_', '-')}-{payload.document_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/applications/{application_id}", response_model=RemoveApplicationResponse)
def remove_application_route(
    application_id: str,
    current_user=Depends(get_current_user),
    connection=Depends(get_db_connection),
):
    return remove_application_controller(connection, str(current_user["user_id"]), application_id)
