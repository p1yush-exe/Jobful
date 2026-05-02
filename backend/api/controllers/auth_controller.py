from api.schemas.auth import AuthResponse, LoginRequest, RefreshRequest, RegisterRequest, ResendVerificationRequest, VerifyEmailRequest
from services.auth_service import login_user, logout_user, refresh_session, register_user, resend_user_verification_code, verify_user_email
from services.google_oauth_service import google_callback, google_start


def register(connection, payload: RegisterRequest) -> AuthResponse:
    return register_user(connection, payload)


def login(connection, payload: LoginRequest) -> AuthResponse:
    return login_user(connection, payload)


def refresh(connection, payload: RefreshRequest) -> AuthResponse:
    return refresh_session(connection, payload)


def verify_email(connection, payload: VerifyEmailRequest):
    return verify_user_email(connection, payload)


def resend_verification(connection, payload: ResendVerificationRequest):
    return resend_user_verification_code(connection, payload)


def start_google_auth():
    return google_start()


def logout(connection, payload: RefreshRequest):
    return logout_user(connection, payload)


def handle_google_callback(connection, code: str | None, state: str | None, error: str | None):
    return google_callback(connection, code, state, error)
