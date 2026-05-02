from fastapi import APIRouter, Depends

from api.controllers.jobs_controller import list_jobs
from api.dependencies.auth import get_current_user
from api.dependencies.common import get_db_connection

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/eligible")
def eligible_jobs_route(current_user=Depends(get_current_user), connection=Depends(get_db_connection)):
    return {"items": list_jobs(connection, str(current_user["user_id"]))}