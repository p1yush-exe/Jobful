from typing import TYPE_CHECKING, Any

from core.config import settings

try:
    import psycopg2
except ImportError:  # pragma: no cover
    psycopg2 = None

if TYPE_CHECKING:
    from psycopg2.extensions import connection as Connection
else:
    Connection = Any


def create_connection() -> Connection:
    if psycopg2 is None:
        raise RuntimeError(
            "psycopg2 is not installed in the active Python environment. "
            "Run the backend with the project venv or `uv run`."
        )

    database_url = settings.database_url
    if not database_url:
        raise RuntimeError("APP_DATABASE_URL or DATABASE_URL is not configured")
    return psycopg2.connect(database_url)
