import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.middleware.auth_context import AuthContextMiddleware
from api.routes.applications import router as applications_router
from api.routes.auth import router as auth_router
from api.routes.cv import router as cv_router
from api.routes.search import router as search_router
from api.routes.onboarding import router as onboarding_router
from api.routes.profile import router as profile_router
from api.routes.health import router as health_router
from core.config import settings
from core.limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Jobful API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(AuthContextMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,  # .env-driven, e.g. http://localhost:3000 for dev, prod URL for Railway
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(onboarding_router, prefix="/api")
app.include_router(cv_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(profile_router, prefix="/api")
app.include_router(applications_router, prefix="/api")

_REPO_ROOT = Path(__file__).resolve().parents[1]
_FRONTEND_ROOT = _REPO_ROOT / "frontend"
_FRONTEND_OUT = _FRONTEND_ROOT / "out"

if _FRONTEND_OUT.exists():
    app.mount("/", StaticFiles(directory=_FRONTEND_OUT, html=True), name="frontend-export")


@app.get("/")
async def root():
    if (_FRONTEND_OUT / "index.html").exists():
        return FileResponse(_FRONTEND_OUT / "index.html")
    return JSONResponse({"status": "jobful-api", "frontend": "next-server"})
