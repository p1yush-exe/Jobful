from typing import Literal

from pydantic import BaseModel


_VALID_STATUSES = {"interested", "applying", "applied", "response", "placed"}

ApplicationStatus = Literal["interested", "applying", "applied", "response", "placed"]
DocumentType = Literal["cv", "cover_letter"]


class TrackJobRequest(BaseModel):
    source: str
    external_id: str
    title: str
    company: str
    location: str = ""
    description: str = ""
    apply_url: str = ""
    source_url: str = ""
    salary_range: str | None = None
    posted_at: str = ""
    status: ApplicationStatus = "interested"


class UpdateStatusRequest(BaseModel):
    status: ApplicationStatus


class ApplicationResponse(BaseModel):
    application_id: str
    status: str
    current_cv_document_id: str | None = None
    current_cover_letter_document_id: str | None = None
    applied_at: str
    updated_at: str
    job_id: str
    job_source: str | None = None
    external_job_key: str | None = None
    title: str
    company: str
    description: str | None = None
    location: str | None
    salary_range: str | None
    apply_url: str | None = None
    source_url: str | None
    is_active: bool = True
    stale_reason: str | None = None
    last_checked_at: str | None = None
    stale_detected_at: str | None = None
    posted_at: str | None


class ApplicationDetailResponse(ApplicationResponse):
    pass


class ApplicationDocumentResponse(BaseModel):
    document_id: str
    application_id: str
    document_type: DocumentType
    title: str
    generation_status: str
    is_current: bool
    content_format: str
    content: str
    rendered_format: str | None = None
    rendered_storage_bucket: str | None = None
    rendered_storage_path: str | None = None
    rendered_mime_type: str | None = None
    rendered_file_size_bytes: int | None = None
    generation_params: dict | None = None
    template_name: str | None = None
    provider: str | None = None
    model_name: str | None = None
    prompt_version: str | None = None
    updated_at: str | None = None
    created_at: str | None = None


class JobNotificationResponse(BaseModel):
    application_id: str
    job_id: str
    status: ApplicationStatus
    kind: Literal["interested_stale", "applied_stale"]
    title: str
    company: str
    message: str
    stale_reason: str | None = None
    stale_detected_at: str | None = None
    can_remove: bool = False


class ApplicationsSummaryResponse(BaseModel):
    total: int
    active: int
    stale: int
    interested: int
    applying: int
    applied: int


class ApplicationsOverviewResponse(BaseModel):
    items: list[ApplicationResponse]
    notifications: list[JobNotificationResponse]
    summary: ApplicationsSummaryResponse
    synced_at: str


class TrackJobResponse(BaseModel):
    application_id: str
    status: str


class PrepareApplyResponse(BaseModel):
    application_id: str
    status: str
    generation_status: Literal["placeholder_pending"]
    apply_url: str | None = None
    documents_to_generate: list[Literal["cv", "cover_letter"]]


class GenerateDocumentRequest(BaseModel):
    document_type: DocumentType


class CompileDocumentRequest(BaseModel):
    document_id: str
    document_type: DocumentType
    html: str


class RemoveApplicationResponse(BaseModel):
    application_id: str
    removed_job_id: str | None = None
