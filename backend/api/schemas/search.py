from pydantic import BaseModel


class JobResult(BaseModel):
    source: str
    external_id: str
    title: str
    company: str
    location: str
    country: str
    description: str
    apply_url: str
    source_url: str
    salary_range: str | None = None
    posted_at: str = ""
    employment_type: str = ""
    work_model: str = ""
    # enriched by filter pipeline
    brief_description: str | None = None
    tech_stack: list[str] = []
    why_fit: str | None = None
    matching_experiences: list[str] = []
    matching_projects: list[str] = []
    gate_provider: str | None = None


class SearchResponse(BaseModel):
    items: list[JobResult]
    total: int
