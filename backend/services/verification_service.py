from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import HTTPException, status
from jwt import InvalidTokenError

from core.config import settings
from services.email_service import send_verification_email


def _verification_salt() -> str:
    return secrets.token_urlsafe(16)


def _verification_hash(code: str, salt: str) -> str:
    digest = hashlib.sha256()
    digest.update(settings.jwt_secret_key.encode("utf-8"))
    digest.update(b":")
    digest.update(salt.encode("utf-8"))
    digest.update(b":")
    digest.update(code.encode("utf-8"))
    return digest.hexdigest()


def generate_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def create_verification_token(email: str, code_hash: str, salt: str, expires_at: datetime) -> str:
    payload = {
        "type": "email_verification",
        "email": email,
        "code_hash": code_hash,
        "salt": salt,
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def build_verification_challenge(email: str) -> tuple[str, str]:
    verification_code = generate_verification_code()
    salt = _verification_salt()
    code_hash = _verification_hash(verification_code, salt)
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.email_verification_code_minutes)
    verification_token = create_verification_token(email, code_hash, salt, expires_at)
    return verification_code, verification_token


def send_registration_verification_email(email: str, full_name: str) -> tuple[str, str]:
    verification_code, verification_token = build_verification_challenge(email)
    send_verification_email(email, full_name, verification_code)
    return verification_code, verification_token


def resend_verification_code(email: str, full_name: str) -> dict[str, object]:
    verification_code, verification_token = send_registration_verification_email(email, full_name)
    return {
        "verification_required": True,
        "email": email,
        "message": "A new verification code has been sent.",
        "verification_token": verification_token,
        "resend_after_seconds": settings.email_verification_resend_cooldown_seconds,
        "debug_code": verification_code if settings.auth_debug_return_codes or not settings.smtp_host else None,
    }


def ensure_verification_token_email(email: str, verification_token: str) -> None:
    try:
        payload = jwt.decode(
            verification_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_exp": False},
        )
    except InvalidTokenError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification token invalid") from error

    if payload.get("type") != "email_verification" or str(payload.get("email", "")).lower() != email.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification token invalid")


def verify_email_code(email: str, code: str, verification_token: str) -> None:
    try:
        payload = jwt.decode(verification_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except InvalidTokenError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code expired or invalid") from error

    if payload.get("type") != "email_verification" or str(payload.get("email", "")).lower() != email.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code expired or invalid")

    expected_hash = str(payload.get("code_hash") or "")
    salt = str(payload.get("salt") or "")
    candidate_hash = _verification_hash(code, salt)
    if not hmac.compare_digest(expected_hash, candidate_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid verification code")
