from pydantic import BaseModel, ConfigDict, Field

_VALID_DEGREE_LEVELS = {"ug", "pg", "phd", "diploma", "other"}


class EducationPreview(BaseModel):
    model_config = ConfigDict(extra="ignore")

    institution: str = ""
    degree: str = ""
    degree_level: str = "ug"   # high_school | diploma | ug | pg | phd | other
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None    # null = currently enrolled
    grade: str | None = None
    description: str | None = None
    tag: str = "research"          # canonical tag — NOT NULL in DB; defaults to 'research'


class ExperiencePreview(BaseModel):
    model_config = ConfigDict(extra="ignore")

    company: str = ""
    location: str | None = None
    role: str = ""
    experience_type: str = "full_time"
    start_date: str = ""
    end_date: str | None = None
    description: str | None = None
    tag: str | None = None
    keywords: list[str] = Field(default_factory=list)


class ProjectPreview(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    description: str | None = None
    github_url: str | None = None
    demo_url: str | None = None
    tag: str | None = None
    keywords: list[str] = Field(default_factory=list)


class ContactPreview(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str | None = None
    phone_number: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    notion_url: str | None = None


class CVPreviewResponse(BaseModel):
    """Returned after upload — shown to user for review. Nothing is stored yet."""
    education: list[EducationPreview]
    experiences: list[ExperiencePreview]
    projects: list[ProjectPreview]
    suggested_tags: list[str]
    contact_details: ContactPreview


class CVConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    education: list[EducationPreview] = Field(default_factory=list)
    experiences: list[ExperiencePreview] = Field(default_factory=list)
    projects: list[ProjectPreview] = Field(default_factory=list)
    suggested_tags: list[str] = Field(default_factory=list)


class CVConfirmResponse(BaseModel):
    education_stored: int
    experiences_stored: int
    projects_stored: int
    suggested_tags: list[str]
