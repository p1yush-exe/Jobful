from api.schemas.applications import (
    ApplicationDetailResponse,
    ApplicationDocumentResponse,
    CompileDocumentRequest,
    GenerateDocumentRequest,
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
from services.application_document_service import (
    compile_html_to_pdf,
    finalize_compiled_document,
    generate_application_document,
    get_application_detail,
    get_compilable_document,
    list_application_documents,
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


def application_detail_controller(connection, user_id: str, application_id: str) -> ApplicationDetailResponse:
    result = get_application_detail(connection, user_id, application_id)
    return ApplicationDetailResponse(**result["application"])


def application_documents_controller(connection, user_id: str, application_id: str) -> dict:
    return {"items": list_application_documents(connection, user_id, application_id)}


def generate_document_controller(connection, user_id: str, application_id: str, payload: GenerateDocumentRequest) -> dict:
    return generate_application_document(connection, user_id, application_id, payload.document_type)


async def compile_document_controller(connection, user_id: str, application_id: str, payload: CompileDocumentRequest) -> dict:
    document = get_compilable_document(connection, user_id, application_id, payload.document_id, payload.document_type)
    pdf_bytes = await compile_html_to_pdf(payload.html)
    result = finalize_compiled_document(
        connection,
        user_id,
        application_id,
        payload.document_id,
        payload.document_type,
        payload.html,
        pdf_bytes,
    )
    return {
        **result,
        "title": document["title"],
        "generation_params": document["generation_params"],
        "pdf_bytes": pdf_bytes,
    }
