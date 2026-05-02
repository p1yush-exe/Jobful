from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

import jwt
import psycopg2
from fastapi import HTTPException, status
from fastapi.responses import RedirectResponse
from jwt import InvalidTokenError

from core.config import settings
from core.security import build_refresh_token, create_access_token, hash_password
from db.executor import fetch_one, fetch_one_commit
from db.query_loader import load_query


_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


def _require_google_config() -> None:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google SSO is not configured")


def _create_state_token() -> str:
    now = datetime.now(UTC)
    payload = {
        "type": "google_oauth_state",
        "nonce": secrets.token_urlsafe(24),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _validate_state_token(state: str) -> None:
    try:
        payload = jwt.decode(state, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state") from error

    if payload.get("type") != "google_oauth_state":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")


def _http_post_form(url: str, form_data: dict[str, str]) -> dict[str, object]:
    encoded_data = urlencode(form_data).encode("utf-8")
    request = Request(url, data=encoded_data, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Google token exchange failed: {body}") from error
    except URLError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to reach Google token endpoint") from error


def _http_get_json(url: str, bearer_token: str) -> dict[str, object]:
    request = Request(url, headers={"Authorization": f"Bearer {bearer_token}"}, method="GET")
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Google profile fetch failed: {body}") from error
    except URLError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to reach Google userinfo endpoint") from error


def _build_frontend_error_redirect(message: str) -> RedirectResponse:
    redirect_target = f"{settings.frontend_base_url.rstrip('/')}/login"
    query = urlencode({"error": message})
    return RedirectResponse(url=f"{redirect_target}?{query}", status_code=status.HTTP_302_FOUND)


def google_start() -> RedirectResponse:
    _require_google_config()
    state_token = _create_state_token()
    query_params = urlencode(
        {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state_token,
            "access_type": "offline",
            "prompt": "select_account",
        }
    )
    return RedirectResponse(url=f"{_GOOGLE_AUTH_URL}?{query_params}", status_code=status.HTTP_302_FOUND)


def _get_or_create_google_user(connection, email: str, full_name: str) -> dict[str, object]:
    existing_user = fetch_one(connection, load_query("auth", "get_user_by_email.sql"), (email,))
    if existing_user is not None:
        return existing_user

    created_user = fetch_one_commit(
        connection,
        load_query("auth", "create_verified_user.sql"),
        (email, hash_password(secrets.token_urlsafe(48)), full_name, "", None),
    )
    if created_user is not None:
        return created_user

    # If insertion races, fallback to re-read.
    existing_user = fetch_one(connection, load_query("auth", "get_user_by_email.sql"), (email,))
    if existing_user is not None:
        return existing_user
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to complete Google sign-in")


def _issue_session_tokens(connection, user_id: str) -> tuple[str, str]:
    for _ in range(2):
        session_id = str(uuid4())
        refresh_token, refresh_jti, refresh_expires_at = build_refresh_token(user_id, session_id)
        try:
            created = fetch_one_commit(
                connection,
                load_query("auth", "create_refresh_session.sql"),
                (session_id, user_id, refresh_jti, refresh_expires_at),
            )
        except psycopg2.IntegrityError:
            connection.rollback()
            continue

        if created is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to create refresh session")

        return create_access_token(user_id, session_id=session_id), refresh_token

    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to create refresh session")


def google_callback(connection, code: str | None, state: str | None, error: str | None) -> RedirectResponse:
    if error:
        return _build_frontend_error_redirect(f"Google sign-in failed: {error}")
    if not code or not state:
        return _build_frontend_error_redirect("Google sign-in failed: missing code or state")

    try:
        _require_google_config()
        _validate_state_token(state)
        token_response = _http_post_form(
            _GOOGLE_TOKEN_URL,
            {
                "code": code,
                "client_id": settings.google_client_id or "",
                "client_secret": settings.google_client_secret or "",
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        access_token = str(token_response.get("access_token") or "")
        if not access_token:
            return _build_frontend_error_redirect("Google sign-in failed: missing access token")

        profile = _http_get_json(_GOOGLE_USERINFO_URL, access_token)
        email = str(profile.get("email") or "").strip().lower()
        email_verified = bool(profile.get("email_verified"))
        full_name = str(profile.get("name") or "").strip() or "Google User"
        if not email or not email_verified:
            return _build_frontend_error_redirect("Google account email is not verified")

        user = _get_or_create_google_user(connection, email, full_name)
        user_id = str(user["user_id"])
        app_access_token, app_refresh_token = _issue_session_tokens(connection, user_id)
    except HTTPException as error_response:
        return _build_frontend_error_redirect(error_response.detail if isinstance(error_response.detail, str) else "Google sign-in failed")

    frontend_target = f"{settings.frontend_base_url.rstrip('/')}/login"
    query = urlencode({"access_token": app_access_token, "refresh_token": app_refresh_token})
    return RedirectResponse(url=f"{frontend_target}?{query}", status_code=status.HTTP_302_FOUND)
