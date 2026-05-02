from pydantic import BaseModel, Field


class ProfileAccountUpdateRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    raw_job_title: str = Field(default="", max_length=200)
    bio: str | None = Field(default=None, max_length=1000)
    phone_number: str | None = Field(default=None, max_length=40)
    github_url: str | None = Field(default=None, max_length=300)
    linkedin_url: str | None = Field(default=None, max_length=300)
    notion_url: str | None = Field(default=None, max_length=300)
    password: str | None = Field(default=None, min_length=8, max_length=128)
