from fastapi import HTTPException, status
import psycopg2
from datetime import UTC, datetime
from uuid import uuid4

from api.schemas.auth import (
    AuthResponse,
    AuthSessionResponse,
    AuthTokens,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    UserResponse,
    VerificationChallengeResponse,
    VerifyEmailRequest,
)
from core.security import build_refresh_token, create_access_token, decode_token, hash_password, verify_password
from core.config import settings
from db.executor import fetch_one, fetch_one_commit
from db.query_loader import load_query
from services.verification_service import ensure_verification_token_email, resend_verification_code, send_registration_verification_email, verify_email_code


def _build_user_response(user_row: dict[str, object]) -> UserResponse:
    selected_tags_count = int(user_row.get("selected_tags_count", 0))
    raw_job_title = str(user_row.get("raw_job_title") or "")
    return UserResponse(
        user_id=str(user_row["user_id"]),
        email=str(user_row["email"]),
        full_name=str(user_row["full_name"]),
        raw_job_title=raw_job_title,
        bio=user_row.get("bio"),
        phone_number=user_row.get("phone_number"),
        github_url=user_row.get("github_url"),
        linkedin_url=user_row.get("linkedin_url"),
        notion_url=user_row.get("notion_url"),
        email_verified_at=user_row.get("email_verified_at"),
        selected_tags_count=selected_tags_count,
        onboarding_complete=bool(raw_job_title) and selected_tags_count > 0,
        cv_uploaded=bool(user_row.get("cv_uploaded", False)),
    )


def _build_tokens(connection, user_id: str) -> AuthTokens:
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

        return AuthTokens(
            access_token=create_access_token(user_id, session_id=session_id),
            refresh_token=refresh_token,
        )

    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to create refresh session")


def _get_user_profile(connection, user_id: str) -> dict[str, object]:
    user = fetch_one(connection, load_query("auth", "get_user_by_id.sql"), (user_id,))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user["selected_tags_count"] = int(user.get("selected_tags_count", 0))
    return user


def _challenge_response(email: str, message: str, verification_token: str, debug_code: str | None = None) -> VerificationChallengeResponse:
    return VerificationChallengeResponse(
        email=email,
        message=message,
        verification_token=verification_token,
        resend_after_seconds=settings.email_verification_resend_cooldown_seconds,
        debug_code=debug_code,
    )


def register_user(connection, payload: RegisterRequest) -> AuthResponse:
    existing = fetch_one(connection, load_query("auth", "get_user_by_email.sql"), (payload.email.lower() ,))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered. Please login instead.")

    verification_code, verification_token = send_registration_verification_email(str(payload.email.lower() ), payload.full_name)
    return _challenge_response(
        email=str(payload.email.lower()),
        message="We sent a verification code to your email. Enter it to finish creating your account.",
        verification_token=verification_token,
        debug_code=verification_code if settings.auth_debug_return_codes or not settings.smtp_host else None,
    )


def login_user(connection, payload: LoginRequest) -> AuthResponse:
    user = fetch_one(connection, load_query("auth", "get_user_by_email.sql"), (payload.email,))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No account found with that email. Please register instead.")

    if not verify_password(payload.password, str(user["password_hash"])):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password.")

    if user.get("email_verified_at") is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not verified")

    profile = _get_user_profile(connection, str(user["user_id"]))
    return AuthSessionResponse(user=_build_user_response(profile), tokens=_build_tokens(connection, str(user["user_id"])))


def refresh_session(connection, payload: RefreshRequest) -> AuthResponse:
    try:
        token_payload = decode_token(payload.refresh_token, expected_type="refresh", require_session=True, require_jti=True)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from error

    user_id = str(token_payload.get("sub") or "")
    session_id = str(token_payload.get("sid") or "")
    token_jti = str(token_payload.get("jti") or "")
    if not user_id or not session_id or not token_jti:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token payload")

    try:
        refresh_session_row = fetch_one(connection, load_query("auth", "get_refresh_session_for_update.sql"), (session_id,))
        if refresh_session_row is None or str(refresh_session_row.get("user_id")) != user_id:
            connection.rollback()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

        if refresh_session_row.get("revoked_at") is not None:
            connection.rollback()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session revoked")

        expires_at = refresh_session_row.get("expires_at")
        if not isinstance(expires_at, datetime) or expires_at <= datetime.now(UTC):
            fetch_one(connection, load_query("auth", "revoke_refresh_session.sql"), ("refresh token expired", session_id))
            connection.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

        current_jti = str(refresh_session_row.get("current_jti") or "")
        if current_jti != token_jti:
            fetch_one(connection, load_query("auth", "revoke_refresh_session.sql"), ("refresh token reuse detected", session_id))
            connection.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token reuse detected. Please login again.")

        next_refresh_token, next_refresh_jti, next_refresh_expires_at = build_refresh_token(user_id, session_id)
        rotated = fetch_one(
            connection,
            load_query("auth", "rotate_refresh_session.sql"),
            (next_refresh_jti, next_refresh_expires_at, session_id),
        )
        if rotated is None:
            connection.rollback()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session rotation failed")

        connection.commit()
    except HTTPException:
        raise
    except Exception:
        connection.rollback()
        raise

    profile = _get_user_profile(connection, str(user_id))
    if profile.get("email_verified_at") is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email not verified")

    return AuthSessionResponse(
        user=_build_user_response(profile),
        tokens=AuthTokens(
            access_token=create_access_token(str(user_id), session_id=session_id),
            refresh_token=next_refresh_token,
        ),
    )


def verify_user_email(connection, payload: VerifyEmailRequest) -> AuthSessionResponse:
    existing = fetch_one(connection, load_query("auth", "get_user_by_email.sql"), (payload.email,))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered. Please login instead.")

    verify_email_code(str(payload.email), payload.code, payload.verification_token)
    try:
        verified_user = fetch_one_commit(
            connection,
            load_query("auth", "create_verified_user.sql"),
            (
                payload.email.lower(),
                hash_password(payload.password),
                payload.full_name,
                payload.raw_job_title or "",
                payload.bio,
            ),
        )
    except psycopg2.IntegrityError:
        verified_user = fetch_one(connection, load_query("auth", "get_user_by_email.sql"), (payload.email.lower() ,))
        if verified_user is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered. Please login instead.")
        raise
    if verified_user is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to verify email")

    profile = _get_user_profile(connection, str(verified_user["user_id"]))
    return AuthSessionResponse(user=_build_user_response(profile), tokens=_build_tokens(connection, str(verified_user["user_id"])))


def logout_user(connection, payload: RefreshRequest) -> dict[str, str]:
    try:
        token_payload = decode_token(payload.refresh_token, expected_type="refresh", require_session=True, require_jti=True)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from error

    session_id = str(token_payload.get("sid") or "")
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token payload")

    fetch_one_commit(connection, load_query("auth", "revoke_refresh_session.sql"), ("logout", session_id))
    return {"detail": "Logged out"}


def resend_user_verification_code(connection, payload: ResendVerificationRequest) -> VerificationChallengeResponse:
    existing = fetch_one(connection, load_query("auth", "get_user_by_email.sql"), (payload.email.lower() ,))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered. Please login instead.")

    ensure_verification_token_email(str(payload.email.lower() ), payload.verification_token)
    challenge = resend_verification_code(str(payload.email.lower() ), payload.full_name)
    if settings.auth_debug_return_codes or not settings.smtp_host:
        return VerificationChallengeResponse(**challenge)

    return VerificationChallengeResponse(**{**challenge, "debug_code": None})
