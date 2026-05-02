from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    raw_job_title: str = Field(default="", max_length=200)
    bio: str | None = Field(default=None, max_length=1000)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=128)
    raw_job_title: str = Field(default="", max_length=200)
    bio: str | None = Field(default=None, max_length=1000)
    code: str = Field(min_length=4, max_length=12)
    verification_token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=120)
    verification_token: str


class UserResponse(BaseModel):
    user_id: str
    email: EmailStr
    full_name: str
    raw_job_title: str
    bio: str | None = None
    phone_number: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    notion_url: str | None = None
    email_verified_at: datetime | None = None
    selected_tags_count: int = 0
    onboarding_complete: bool = False
    cv_uploaded: bool = False
    experience_years: int = -1


class AuthTokens(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class VerificationChallengeResponse(BaseModel):
    verification_required: Literal[True] = True
    email: EmailStr
    message: str
    verification_token: str
    resend_after_seconds: int = 60
    debug_code: str | None = None


class AuthSessionResponse(BaseModel):
    verification_required: Literal[False] = False
    user: UserResponse
    tokens: AuthTokens


AuthResponse = AuthSessionResponse | VerificationChallengeResponse
