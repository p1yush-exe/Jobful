from functools import lru_cache
import json
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str | None = Field(default=None, validation_alias=AliasChoices("APP_DATABASE_URL", "DATABASE_URL"))
    allowed_origins_raw: str = Field(default="http://localhost:3000", alias="ALLOWED_ORIGINS")
    jwt_secret_key: str = Field(default="dev-only-change-me", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_active_kid: str = Field(default="v1", alias="JWT_ACTIVE_KID")
    jwt_keys_json: str | None = Field(default=None, alias="JWT_KEYS_JSON")
    jwt_allow_legacy_no_kid: bool = Field(default=True, alias="JWT_ALLOW_LEGACY_NO_KID")
    jwt_issuer: str = Field(default="jobful-api", alias="JWT_ISSUER")
    jwt_audience: str = Field(default="jobful-client", alias="JWT_AUDIENCE")
    access_token_minutes: int = Field(default=15, alias="ACCESS_TOKEN_MINUTES")
    refresh_token_days: int = Field(default=7, alias="REFRESH_TOKEN_DAYS")
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    smtp_from_email: str | None = Field(default=None, alias="SMTP_FROM_EMAIL")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")
    email_verification_code_minutes: int = Field(default=10, alias="EMAIL_VERIFICATION_CODE_MINUTES")
    email_verification_max_attempts: int = Field(default=5, alias="EMAIL_VERIFICATION_MAX_ATTEMPTS")
    email_verification_resend_cooldown_seconds: int = Field(default=60, alias="EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS")
    auth_debug_return_codes: bool = Field(default=False, alias="AUTH_DEBUG_RETURN_CODES")
    frontend_base_url: str = Field(default="http://localhost:3000", alias="FRONTEND_BASE_URL")
    google_client_id: str | None = Field(default=None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: str | None = Field(default=None, alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(default="http://localhost:8000/api/auth/google/callback", alias="GOOGLE_REDIRECT_URI")
    groq_api_key: str | None = Field(default=None, alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    cv_max_bytes: int = Field(default=5 * 1024 * 1024, alias="CV_MAX_BYTES")
    cv_min_text_chars: int = Field(default=200, alias="CV_MIN_TEXT_CHARS")
    supabase_url: str | None = Field(default=None, alias="SUPABASE_URL")
    supabase_service_role_key: str | None = Field(default=None, alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_storage_bucket: str = Field(default="generated-documents", alias="SUPABASE_STORAGE_BUCKET")
    rapidapi_key: str | None = Field(default=None, alias="RAPIDAPI_KEY")
    adzuna_app_id: str | None = Field(default=None, alias="ADZUNA_APP_ID")
    adzuna_app_key: str | None = Field(default=None, alias="ADZUNA_APP_KEY")
    job_search_pages: int = Field(default=2, alias="JOB_SEARCH_PAGES")
    job_search_delay: float = Field(default=0.5, alias="JOB_SEARCH_DELAY")

    @field_validator("allowed_origins_raw", mode="before")
    @classmethod
    def normalize_allowed_origins(cls, value: str | list[str]) -> str:
        if isinstance(value, list):
            return ",".join(origin.strip() for origin in value if origin and origin.strip())

        if not isinstance(value, str):
            return "http://localhost:3000"

        stripped = value.strip()
        if not stripped:
            return "http://localhost:3000"

        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return stripped

            if isinstance(parsed, list):
                return ",".join(str(origin).strip() for origin in parsed if str(origin).strip())

        return stripped

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins_raw.split(",") if origin.strip()]

    @property
    def jwt_signing_keys(self) -> dict[str, str]:
        if not self.jwt_keys_json:
            return {self.jwt_active_kid: self.jwt_secret_key}

        try:
            parsed = json.loads(self.jwt_keys_json)
        except json.JSONDecodeError as error:
            raise ValueError("JWT_KEYS_JSON must be valid JSON") from error

        if not isinstance(parsed, dict) or not parsed:
            raise ValueError("JWT_KEYS_JSON must be a non-empty JSON object of {kid: secret}")

        keys: dict[str, str] = {}
        for kid, secret in parsed.items():
            kid_text = str(kid).strip()
            secret_text = str(secret).strip() if secret is not None else ""
            if not kid_text or not secret_text:
                raise ValueError("JWT_KEYS_JSON contains an empty kid or secret")
            keys[kid_text] = secret_text

        if self.jwt_active_kid not in keys:
            raise ValueError("JWT_ACTIVE_KID must exist in JWT_KEYS_JSON")

        return keys


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
