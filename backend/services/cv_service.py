"""CV ingestion service.

Two-step flow:
1. process_cv_upload()  → extract text → Groq parse → return preview dict (NO DB write)
2. store_confirmed_cv_data() → user-confirmed/edited data → transactional DB write
"""

from __future__ import annotations

import io
import json
import re
from datetime import date
from typing import Any

import fitz  # PyMuPDF
from fastapi import HTTPException, status

from core.config import settings
from db.executor import fetch_all, fetch_one
from db.query_loader import load_query


_VALID_EXPERIENCE_TYPES = {
    "internship",
    "freelance",
    "full_time",
    "part_time",
    "unpaid_internship",
    "advisor",
}

_VALID_DEGREE_LEVELS = {"high_school", "diploma", "ug", "pg", "phd", "other"}

_KEYWORD_ALIAS: dict[str, str] = {
    "reactjs": "react",
    "react.js": "react",
    "node.js": "node",
    "nodejs": "node",
    "next.js": "next",
    "nextjs": "next",
    "vue.js": "vue",
    "vuejs": "vue",
    "tensorflow.js": "tensorflowjs",
    "postgres": "postgresql",
    "adobe photoshop": "photoshop",
    "adobe illustrator": "illustrator",
    "adobe premiere": "premiere",
    "adobe premiere pro": "premiere",
    "premiere pro": "premiere",
    "after effects": "aftereffects",
}

_EMAIL_REGEX = re.compile(r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[A-Za-z]{2,}\b")
_PHONE_REGEX = re.compile(r"(?:(?:\+?\d[\d().\-\s]{8,}\d))")
_LINKEDIN_REGEX = re.compile(r"(?i)\b(?:https?://)?(?:www\.)?linkedin\.com/[^\s<>()]+")
_GITHUB_REGEX = re.compile(r"(?i)\b(?:https?://)?(?:www\.)?github\.com/[^\s<>()]+")
_NOTION_REGEX = re.compile(r"(?i)\b(?:https?://)?(?:www\.)?(?:notion\.so|notion\.site)/[^\s<>()]+")


def normalize_keyword(raw: str) -> str:
    cleaned = (raw or "").strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return _KEYWORD_ALIAS.get(cleaned, cleaned)


def _clean_url(raw: str) -> str | None:
    value = (raw or "").strip().rstrip(".,;:)]}>\"'")
    if not value:
        return None
    if value.startswith("www."):
        value = f"https://{value}"
    elif not re.match(r"(?i)^https?://", value):
        value = f"https://{value}"
    return value


def _extract_first_url(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    if not match:
        return None
    return _clean_url(match.group(0))


def _extract_phone_number(text: str) -> str | None:
    for match in _PHONE_REGEX.finditer(text):
        candidate = match.group(0).strip()
        digits = re.sub(r"\D", "", candidate)
        if 10 <= len(digits) <= 15:
            return re.sub(r"\s+", " ", candidate)
    return None


def extract_contact_details(text: str) -> dict[str, str | None]:
    return {
        "email": next((m.group(0).strip() for m in _EMAIL_REGEX.finditer(text)), None),
        "phone_number": _extract_phone_number(text),
        "github_url": _extract_first_url(_GITHUB_REGEX, text),
        "linkedin_url": _extract_first_url(_LINKEDIN_REGEX, text),
        "notion_url": _extract_first_url(_NOTION_REGEX, text),
    }


# ── PDF extraction ────────────────────────────────────────────────────────────

def extract_text(file_bytes: bytes) -> str:
    """Extract plain text from PDF in memory. Never writes to disk."""
    try:
        doc = fitz.open(stream=io.BytesIO(file_bytes), filetype="pdf")
    except Exception as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not read PDF file") from error
    try:
        parts: list[str] = []
        for page in doc:
            parts.append(page.get_text("text"))
        return "\n".join(parts).strip()
    finally:
        doc.close()


# ── Groq parsing ──────────────────────────────────────────────────────────────

def _load_canonical_tag_names(connection) -> list[str]:
    rows = fetch_all(connection, load_query("cv", "get_all_canonical_tag_names.sql"), ())
    return [r["tag_name"] for r in rows]


def _build_groq_prompt(text: str, canonical_tags: list[str]) -> str:
    tag_list = ", ".join(canonical_tags)
    valid_types = ", ".join(sorted(_VALID_EXPERIENCE_TYPES))
    return f"""You are a CV parser. Extract structured data from the following CV text.

Allowed canonical tags (ONLY these for "tag" fields and "suggested_user_tags"):
{tag_list}

Allowed experience_type values: {valid_types}
Allowed degree_level values: high_school, diploma, ug (bachelor/undergraduate), pg (master/postgraduate/MBA), phd (doctorate), other

Return STRICT JSON (no prose, no markdown fences):
{{
  "education": [
    {{
      "institution": "string",
      "degree": "string (e.g. Bachelor of Technology, Master of Science, High School Diploma)",
      "degree_level": "one of: high_school | diploma | ug | pg | phd | other",
      "field_of_study": "string or null",
      "start_date": "YYYY-MM-DD or null",
      "end_date": "YYYY-MM-DD or null if current/ongoing",
      "grade": "string or null (GPA, percentage, grade, etc.)",
      "description": "string or null",
      "tag": "one canonical tag most relevant to this qualification"
    }}
  ],
  "experiences": [
    {{
      "company": "string",
      "location": "string or null",
      "role": "string",
      "experience_type": "one of allowed types",
      "start_date": "YYYY-MM-DD",
      "end_date": "YYYY-MM-DD or null if current",
      "description": "string",
      "tag": "one canonical tag",
      "keywords": ["lowercase tech keywords"]
    }}
  ],
  "projects": [
    {{
      "name": "string",
      "description": "string",
      "tag": "one canonical tag",
      "keywords": ["lowercase tech keywords"]
    }}
  ],
  "suggested_user_tags": ["up to 5 canonical tags"]
}}

Rules:
- Dates: assume day=01 if only month/year given. Year-only → YYYY-01-01.
- tag MUST be exactly one of the allowed canonical tags.
- keywords: lowercase, no version numbers, no duplicates.
- Return empty arrays if nothing found.
- Education is CRITICAL — extract all degrees, diplomas, and certifications.

CV TEXT:
\"\"\"
{text}
\"\"\"
"""


def parse_cv_with_groq(text: str, canonical_tags: list[str]) -> dict[str, Any]:
    """Call Groq. Returns parsed dict. Does NOT touch DB."""
    if not settings.groq_api_key:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="GROQ_API_KEY not configured")

    try:
        from langchain_groq import ChatGroq
    except ImportError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="langchain-groq not installed") from error

    def _make_llm(json_mode: bool):
        kwargs: dict[str, Any] = {"model": settings.groq_model, "api_key": settings.groq_api_key, "temperature": 0.0}
        if json_mode:
            kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
        return ChatGroq(**kwargs)

    prompt = _build_groq_prompt(text, canonical_tags)
    try:
        response = _make_llm(json_mode=True).invoke(prompt)
    except Exception:
        try:
            response = _make_llm(json_mode=False).invoke(prompt)
        except Exception as error:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Groq call failed: {error}") from error

    raw = getattr(response, "content", None) or str(response)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    if not cleaned.startswith("{"):
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            cleaned = m.group(0)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Groq returned invalid JSON: {error}") from error

    parsed.setdefault("experiences", [])
    parsed.setdefault("projects", [])
    parsed.setdefault("suggested_user_tags", [])
    return parsed


# ── Step 1: Preview (NO DB write) ─────────────────────────────────────────────

def process_cv_upload(connection, user_id: str, file_bytes: bytes) -> dict[str, Any]:
    """Extract text → Groq parse → return preview dict. NOTHING written to DB."""
    text = extract_text(file_bytes)
    if len(text) < settings.cv_min_text_chars:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="CV appears to be a scanned image or empty. Paste text manually or upload a text-based PDF.",
        )
    canonical_tags = _load_canonical_tag_names(connection)
    parsed = parse_cv_with_groq(text, canonical_tags)
    contact_details = extract_contact_details(text)

    canonical_set = set(canonical_tags)

    def _to_list(key: str) -> list:
        v = parsed.get(key) or []
        return v if isinstance(v, list) else []

    # ── education ─────────────────────────────────────────────────────────────
    clean_edu = []
    for edu in _to_list("education"):
        if not isinstance(edu, dict):
            continue
        if edu.get("degree_level") not in _VALID_DEGREE_LEVELS:
            edu["degree_level"] = "other"
        edu.setdefault("institution", "")
        edu.setdefault("degree", "")
        if not edu.get("institution"):
            edu["institution"] = ""
        if not edu.get("degree"):
            edu["degree"] = ""
        # validate tag; default to 'research' if invalid/missing
        if edu.get("tag") not in canonical_set:
            edu["tag"] = "research"
        clean_edu.append(edu)

    # ── experiences ──────────────────────────────────────────────────────────
    clean_exps = []
    for exp in _to_list("experiences"):
        if not isinstance(exp, dict):
            continue
        exp["keywords"] = list({normalize_keyword(k) for k in (exp.get("keywords") or []) if k})
        if exp.get("tag") not in canonical_set:
            exp["tag"] = None
        exp.setdefault("company", "")
        exp.setdefault("role", "")
        exp.setdefault("experience_type", "full_time")
        exp.setdefault("start_date", "")
        if exp.get("company") is None:
            exp["company"] = ""
        if exp.get("role") is None:
            exp["role"] = ""
        if exp.get("experience_type") not in _VALID_EXPERIENCE_TYPES:
            exp["experience_type"] = "full_time"
        if exp.get("start_date") is None:
            exp["start_date"] = ""
        clean_exps.append(exp)

    # ── projects ─────────────────────────────────────────────────────────────
    clean_projs = []
    for proj in _to_list("projects"):
        if not isinstance(proj, dict):
            continue
        proj["keywords"] = list({normalize_keyword(k) for k in (proj.get("keywords") or []) if k})
        if proj.get("tag") not in canonical_set:
            proj["tag"] = None
        proj.setdefault("name", "")
        if proj.get("name") is None:
            proj["name"] = ""
        clean_projs.append(proj)

    suggested = [t for t in parsed.get("suggested_user_tags", []) if isinstance(t, str) and t in canonical_set][:5]

    return {
        "education": clean_edu,
        "experiences": clean_exps,
        "projects": clean_projs,
        "suggested_tags": suggested,
        "contact_details": contact_details,
    }


# ── Step 2: Commit confirmed data ─────────────────────────────────────────────

def _parse_date(value: Any) -> date | None:
    if not value or value in ("null", "None"):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _resolve_tag_id(connection, tag_name: str | None) -> str | None:
    if not tag_name:
        return None
    row = fetch_one(connection, load_query("cv", "get_canonical_tag_by_name.sql"), (tag_name,))
    return str(row["tag_id"]) if row else None


def _get_or_create_keyword_id(cursor, keyword: str) -> str:
    cursor.execute(load_query("cv", "get_or_create_keyword.sql"), (keyword, keyword))
    return str(cursor.fetchone()[0])


def store_confirmed_cv_data(connection, user_id: str, confirmed: dict[str, Any]) -> dict[str, Any]:
    """
    Write user-confirmed (and possibly user-edited) CV data to DB.
    Single transaction — rollback on any failure, user keeps prior data.
    """
    canonical_set = set(_load_canonical_tag_names(connection))

    cv_tag_ids: set[str] = set()
    for edu in confirmed.get("education", []):
        tag_name = edu.get("tag") or "research"
        if tag_name in canonical_set:
            row = fetch_one(connection, load_query("cv", "get_canonical_tag_by_name.sql"), (tag_name,))
            if row:
                cv_tag_ids.add(str(row["tag_id"]))
    for exp in confirmed.get("experiences", []):
        tn = exp.get("tag")
        if tn and tn in canonical_set:
            row = fetch_one(connection, load_query("cv", "get_canonical_tag_by_name.sql"), (tn,))
            if row:
                cv_tag_ids.add(str(row["tag_id"]))
    for proj in confirmed.get("projects", []):
        tn = proj.get("tag")
        if tn and tn in canonical_set:
            row = fetch_one(connection, load_query("cv", "get_canonical_tag_by_name.sql"), (tn,))
            if row:
                cv_tag_ids.add(str(row["tag_id"]))

    for sug_name in confirmed.get("suggested_tags", []):
        if isinstance(sug_name, str) and sug_name in canonical_set:
            row = fetch_one(connection, load_query("cv", "get_canonical_tag_by_name.sql"), (sug_name,))
            if row:
                cv_tag_ids.add(str(row["tag_id"]))

    canonical_tag_ids = [
        str(row["tag_id"])
        for row in fetch_all(connection, load_query("onboarding", "get_canonical_tags.sql"), ())
    ]

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(load_query("cv", "clear_user_education.sql"), (user_id,))
                cursor.execute(load_query("cv", "clear_user_cv_data.sql"), (user_id,))
                cursor.execute(load_query("cv", "clear_user_projects.sql"), (user_id,))

                # ── education ─────────────────────────────────────────────────
                edu_count = 0
                for edu in confirmed.get("education", []):
                    institution = (edu.get("institution") or "").strip()
                    degree = (edu.get("degree") or "").strip()
                    if not institution or not degree:
                        continue
                    degree_level = edu.get("degree_level") or "other"
                    if degree_level not in _VALID_DEGREE_LEVELS:
                        degree_level = "other"
                    # resolve tag — fallback to 'research' to satisfy NOT NULL
                    tag_name = edu.get("tag") or "research"
                    if tag_name not in canonical_set:
                        tag_name = "research"
                    edu_tag_row = fetch_one(connection, load_query("cv", "get_canonical_tag_by_name.sql"), (tag_name,))
                    if not edu_tag_row:
                        continue  # 'research' not in canonical_tags — skip rather than fail
                    cursor.execute(
                        load_query("cv", "insert_education.sql"),
                        (
                            user_id,
                            institution,
                            degree,
                            degree_level,
                            edu.get("field_of_study") or None,
                            _parse_date(edu.get("start_date")),
                            _parse_date(edu.get("end_date")),
                            edu.get("grade") or None,
                            edu.get("description") or None,
                            str(edu_tag_row["tag_id"]),
                        ),
                    )
                    edu_count += 1

                exp_count = 0
                for exp in confirmed.get("experiences", []):
                    exp_type = exp.get("experience_type")
                    if exp_type not in _VALID_EXPERIENCE_TYPES:
                        continue
                    company = (exp.get("company") or "").strip()
                    role = (exp.get("role") or "").strip()
                    if not company or not role:
                        continue
                    start = _parse_date(exp.get("start_date"))
                    if start is None:
                        continue

                    tag_name = exp.get("tag") if exp.get("tag") in canonical_set else None
                    tag_id = _resolve_tag_id(connection, tag_name)

                    cursor.execute(
                        load_query("cv", "insert_experience.sql"),
                        (user_id, company, exp.get("location") or None, role, exp_type,
                         start, _parse_date(exp.get("end_date")), exp.get("description") or None, tag_id),
                    )
                    experience_id = cursor.fetchone()[0]
                    exp_count += 1

                    seen_kw: set[str] = set()
                    for kw in exp.get("keywords", []) or []:
                        norm = normalize_keyword(str(kw))
                        if not norm or norm in seen_kw:
                            continue
                        seen_kw.add(norm)
                        kw_id = _get_or_create_keyword_id(cursor, norm)
                        cursor.execute(load_query("cv", "insert_experience_keyword.sql"), (experience_id, kw_id))

                proj_count = 0
                for proj in confirmed.get("projects", []):
                    name = (proj.get("name") or "").strip()
                    if not name:
                        continue
                    tag_name = proj.get("tag") if proj.get("tag") in canonical_set else None
                    tag_id = _resolve_tag_id(connection, tag_name)

                    cursor.execute(
                        load_query("cv", "insert_project.sql"),
                        (user_id, name, proj.get("description") or None, tag_id),
                    )
                    project_id = cursor.fetchone()[0]
                    proj_count += 1

                    seen_kw = set()
                    for kw in proj.get("keywords", []) or []:
                        norm = normalize_keyword(str(kw))
                        if not norm or norm in seen_kw:
                            continue
                        seen_kw.add(norm)
                        kw_id = _get_or_create_keyword_id(cursor, norm)
                        cursor.execute(load_query("cv", "insert_project_keyword.sql"), (project_id, kw_id))

                for tag_id in canonical_tag_ids:
                    cursor.execute(load_query("onboarding", "insert_user_assigned_tag.sql"), (user_id, tag_id))
                for tag_id in cv_tag_ids:
                    cursor.execute(load_query("onboarding", "insert_user_selected_tag.sql"), (user_id, tag_id))

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store CV data: {error}",
        ) from error

    # mark cv as uploaded on the user row
    with connection.cursor() as cursor:
        cursor.execute(load_query("auth", "mark_cv_uploaded.sql"), (user_id,))
    connection.commit()

    suggested = [t for t in confirmed.get("suggested_tags", []) if isinstance(t, str) and t in canonical_set][:5]
    return {
        "education_stored": edu_count,
        "experiences_stored": exp_count,
        "projects_stored": proj_count,
        "suggested_tags": suggested,
    }
