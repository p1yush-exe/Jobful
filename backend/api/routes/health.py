from fastapi import APIRouter

from api.controllers.health_controller import health_check

router = APIRouter(tags=["health"])

router.get("/health")(health_check)
