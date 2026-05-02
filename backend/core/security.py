from datetime import UTC, datetime, timedelta
from uuid import uuid4

import bcrypt
import jwt
from jwt import InvalidTokenError

from core.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), password_hash.encode())


def _resolve_signing_key_for_encode() -> tuple[str, str]:
    keys = settings.jwt_signing_keys
    active_kid = settings.jwt_active_kid
    if active_kid not in keys:
        raise ValueError("Active JWT key id is not configured")
    return active_kid, keys[active_kid]


def _resolve_signing_key_for_decode(token: str) -> str:
    keys = settings.jwt_signing_keys
    try:
        header = jwt.get_unverified_header(token)
    except InvalidTokenError as error:
        raise ValueError("Invalid token") from error

    kid = header.get("kid")
    if isinstance(kid, str) and kid in keys:
        return keys[kid]

    if kid and kid not in keys:
        raise ValueError("Unknown token key id")

    if settings.jwt_allow_legacy_no_kid:
        return settings.jwt_secret_key

    raise ValueError("Token key id missing")


def _create_token(subject: str, token_type: str, expires_delta: timedelta, extra_claims: dict[str, object] | None = None) -> str:
    now = datetime.now(UTC)
    exp = now + expires_delta
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    if extra_claims:
        payload.update(extra_claims)
    kid, signing_key = _resolve_signing_key_for_encode()
    return jwt.encode(payload, signing_key, algorithm=settings.jwt_algorithm, headers={"kid": kid})


def create_access_token(subject: str, session_id: str | None = None) -> str:
    extra_claims: dict[str, object] = {}
    if session_id:
        extra_claims["sid"] = session_id
    return _create_token(subject, "access", timedelta(minutes=settings.access_token_minutes), extra_claims=extra_claims)


def build_refresh_token(subject: str, session_id: str) -> tuple[str, str, datetime]:
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=settings.refresh_token_days)
    jti = str(uuid4())
    token = _create_token(
        subject,
        "refresh",
        timedelta(days=settings.refresh_token_days),
        extra_claims={"sid": session_id, "jti": jti},
    )
    return token, jti, expires_at


def decode_token(
    token: str,
    expected_type: str | None = None,
    require_session: bool = False,
    require_jti: bool = False,
) -> dict[str, object]:
    signing_key = _resolve_signing_key_for_decode(token)
    try:
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "sub", "type", "iss", "aud"]},
        )
    except InvalidTokenError as error:
        raise ValueError("Invalid token") from error

    if expected_type is not None and payload.get("type") != expected_type:
        raise ValueError("Unexpected token type")
    if require_session and not payload.get("sid"):
        raise ValueError("Missing token session id")
    if require_jti and not payload.get("jti"):
        raise ValueError("Missing token id")

    return payload
