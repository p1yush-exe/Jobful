from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api.dependencies.common import get_db_connection
from core.security import decode_token
from db.executor import fetch_one
from db.query_loader import load_query


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    connection=Depends(get_db_connection),
):
    payload = getattr(request.state, "auth_payload", None)
    auth_error = getattr(request.state, "auth_error", None)
    if auth_error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if payload is None:
        if credentials is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        try:
            payload = decode_token(credentials.credentials)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from error

    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = fetch_one(connection, load_query("auth", "get_user_by_id.sql"), (user_id,))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if user.get("email_verified_at") is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not verified")

    user["selected_tags_count"] = int(user.get("selected_tags_count", 0))
    user["onboarding_complete"] = bool(user.get("raw_job_title")) and user["selected_tags_count"] > 0
    return user
