from fastapi import APIRouter, Depends, Query, Request

from api.dependencies.auth import get_current_user
from api.dependencies.common import get_db_connection
from api.schemas.search import JobResult, SearchResponse
from core.limiter import limiter
from services.job_filter_service import run_filter_pipeline
from services.search_service import search_jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/search", response_model=SearchResponse)
@limiter.limit("30/minute")
def job_search_route(
    request: Request,
    q: str = Query(..., min_length=1, description="Search query (tag name or role)"),
    location: str = Query(default="", description="City or region"),
    country: str = Query(default="in", description="Country code"),
    source: str = Query(default="all", description="jsearch | adzuna | all"),
    employment_type: str = Query(default="", description="FULLTIME | PARTTIME | CONTRACTOR | INTERN"),
    work_model: str = Query(default="", description="remote | hybrid | onsite"),
    date_posted: str = Query(default="month", description="today | 3days | week | month"),
    salary_min: int = Query(default=0, description="Minimum salary (0 = any)"),
    allow_unspecified_pay: bool = Query(default=True, description="Include jobs with no stated salary"),
    current_user=Depends(get_current_user),
    connection=Depends(get_db_connection),
):
    raw_jobs = search_jobs(
        query=q,
        location=location,
        country=country,
        source=source,
        employment_type=employment_type,
        work_model=work_model,
        date_posted=date_posted,
        salary_min=salary_min,
        allow_unspecified_pay=allow_unspecified_pay,
    )

    filters = {
        "country": country,
        "salary_min": salary_min,
        "employment_type": employment_type,
        "work_model": work_model,
    }

    filtered = run_filter_pipeline(
        connection=connection,
        user_id=str(current_user["user_id"]),
        raw_jobs=raw_jobs,
        filters=filters,
    )

    items = [
        JobResult(
            source=j["source"],
            external_id=j["external_id"],
            title=j["title"],
            company=j["company"],
            location=j["location"],
            country=j["country"],
            description=j["description"],
            apply_url=j["apply_url"],
            source_url=j["source_url"],
            salary_range=j.get("salary_range"),
            posted_at=j.get("posted_at") or "",
            employment_type=j.get("employment_type") or "",
            work_model=j.get("work_model") or "",
            brief_description=j.get("brief_description"),
            tech_stack=j.get("tech_stack") or [],
            why_fit=j.get("why_fit"),
            matching_experiences=j.get("matching_experiences") or [],
            matching_projects=j.get("matching_projects") or [],
            gate_provider=j.get("gate_provider"),
        )
        for j in filtered
    ]
    return SearchResponse(items=items, total=len(items))
