from fastapi import APIRouter, Depends

from api.controllers.auth_controller import handle_google_callback, login, logout, refresh, resend_verification, register, start_google_auth, verify_email
from api.dependencies.auth import get_current_user
from api.dependencies.common import get_db_connection
from api.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    UserResponse,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
def register_route(payload: RegisterRequest, connection=Depends(get_db_connection)):
    return register(connection, payload)


@router.post("/login", response_model=AuthResponse)
def login_route(payload: LoginRequest, connection=Depends(get_db_connection)):
    return login(connection, payload)


@router.post("/refresh", response_model=AuthResponse)
def refresh_route(payload: RefreshRequest, connection=Depends(get_db_connection)):
    return refresh(connection, payload)


@router.post("/verify-email", response_model=AuthResponse)
def verify_email_route(payload: VerifyEmailRequest, connection=Depends(get_db_connection)):
    return verify_email(connection, payload)


@router.post("/resend-verification")
def resend_verification_route(payload: ResendVerificationRequest, connection=Depends(get_db_connection)):
    return resend_verification(connection, payload)


@router.post("/logout")
def logout_route(payload: RefreshRequest, connection=Depends(get_db_connection)):
    return logout(connection, payload)


@router.get("/me", response_model=UserResponse)
def me_route(current_user=Depends(get_current_user)):
    return current_user


@router.post("/session", response_model=UserResponse)
def session_route(current_user=Depends(get_current_user)):
    return current_user


@router.get("/google/start")
def google_start_route():
    return start_google_auth()


@router.get("/google/callback")
def google_callback_route(code: str | None = None, state: str | None = None, error: str | None = None, connection=Depends(get_db_connection)):
    return handle_google_callback(connection, code, state, error)
