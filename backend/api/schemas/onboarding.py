from uuid import UUID

from pydantic import BaseModel, Field


class ProfileUpdateRequest(BaseModel):
    raw_job_title: str = Field(min_length=1, max_length=200)
    bio: str | None = Field(default=None, max_length=1000)


class TagResponse(BaseModel):
    tag_id: UUID
    tag_name: str


class SelectedTagsRequest(BaseModel):
    tag_ids: list[UUID] = Field(min_length=1)  # no upper limit; limit applied at job-search time


class OnboardingStateResponse(BaseModel):
    user_id: str
    raw_job_title: str
    bio: str | None = None
    recommended_tags: list[TagResponse]
    assigned_tags: list[TagResponse]
    selected_tags: list[TagResponse]


class EligibleJobResponse(BaseModel):
    job_id: UUID
    title: str
    company: str
    location: str | None = None
    salary_range: str | None = None
    posted_at: str