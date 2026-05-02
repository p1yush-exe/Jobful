from __future__ import annotations

import asyncio
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from fastapi import HTTPException, status
from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.sync_api import sync_playwright

from core.config import settings
from db.executor import execute, fetch_all, fetch_one
from db.query_loader import load_query
from services.groq_client import GroqClientError, call_groq_json


DOCUMENT_TYPES = {"cv", "cover_letter"}
TECHNICAL_TAGS = {
    "frontend",
    "backend",
    "fullstack",
    "mobile",
    "embedded-systems",
    "systems-programming",
    "devops",
    "cloud",
    "security",
    "testing",
    "software development",
    "ai-ml",
    "data-science",
    "data-engineering",
    "automation",
    "robotics",
    "blockchain",
    "ios",
    "android",
    "game-development",
    "ar-vr",
    "fintech",
}
NON_TECHNICAL_TAGS = {
    "graphic-design",
    "motion-design",
    "video-editing",
    "content-creation",
    "photography",
    "3d-modelling",
    "product-design",
    "ui-ux",
    "product-management",
    "consulting",
    "technical-writing",
    "sales-growth",
    "operations",
    "hr-people",
    "legal-compliance",
}

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
)

_GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def _now_text() -> str:
    return datetime.now(timezone.utc).isoformat()


def _serialize_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key in (
        "applied_at",
        "updated_at",
        "posted_at",
        "last_checked_at",
        "stale_detected_at",
        "created_at",
    ):
        if key in out and out[key] is not None and not isinstance(out[key], str):
            out[key] = str(out[key])
    for key in ("application_id", "job_id", "user_id", "current_cv_document_id", "current_cover_letter_document_id"):
        if key in out and out[key] is not None:
            out[key] = str(out[key])
    return out


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_keyword(value: str) -> str:
    cleaned = _normalize_text(value).lower()
    cleaned = re.sub(r"[^a-z0-9+\- ]+", "", cleaned)
    return cleaned


def _tokenize(text: str) -> set[str]:
    return {token for token in re.split(r"\W+", text.lower()) if len(token) > 2}


def _compile_job_text(job: dict[str, Any]) -> str:
    return " ".join(
        filter(
            None,
            [
                _normalize_text(job.get("title")),
                _normalize_text(job.get("company")),
                _normalize_text(job.get("description")),
                " ".join(job.get("tags") or []),
            ],
        )
    )


def _fallback_job_keywords(job: dict[str, Any]) -> list[str]:
    tokens = [_normalize_keyword(token) for token in re.split(r"\W+", _compile_job_text(job))]
    keywords: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if not token or len(token) < 2 or token in seen:
            continue
        seen.add(token)
        keywords.append(token)
    return keywords[:16]


def _extract_job_keywords(job: dict[str, Any]) -> list[str]:
    prompt = (
        "Extract the most relevant job keywords from the posting.\n"
        "Return ONLY a JSON object with a key named keywords containing an array of strings.\n"
        "Prefer skills, tools, frameworks, domain phrases, and role-specific nouns.\n"
        f"TITLE: {job.get('title')}\n"
        f"DESCRIPTION: {str(job.get('description') or '')[:3500]}\n"
    )
    try:
        payload = call_groq_json(prompt, model=_GROQ_MODEL)
        raw_keywords = payload.get("keywords") if isinstance(payload, dict) else None
        if isinstance(raw_keywords, list):
            cleaned: list[str] = []
            seen: set[str] = set()
            for item in raw_keywords:
                keyword = _normalize_keyword(str(item))
                if keyword and keyword not in seen:
                    seen.add(keyword)
                    cleaned.append(keyword)
            if cleaned:
                return cleaned[:16]
    except (GroqClientError, Exception):
        pass
    return _fallback_job_keywords(job)


def _call_groq_text(prompt: str, max_tokens: int = 450) -> str:
    api_key = settings.groq_api_key
    if not api_key:
        raise GroqClientError("GROQ_API_KEY is missing.")
    body = json.dumps(
        {
            "model": _GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.25,
            "max_tokens": max_tokens,
        }
    ).encode("utf-8")
    request = Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise GroqClientError(f"groq_http_{exc.code}:{body_text[:300]}") from exc
    except URLError as exc:
        raise GroqClientError(f"groq_network_error:{exc.reason}") from exc

    try:
        return str(raw["choices"][0]["message"]["content"]).strip()
    except Exception as exc:
        raise GroqClientError(f"groq_invalid_response:{raw}") from exc


def _best_match_score(item: dict[str, Any], job_tags: set[str], job_keywords: set[str]) -> tuple[int, str]:
    score = 0
    tag = _normalize_text(item.get("tag")).lower()
    if tag and tag in job_tags:
        score += 3
    keywords = {_normalize_keyword(keyword) for keyword in (item.get("keywords") or [])}
    score += sum(1 for keyword in keywords if keyword and keyword in job_keywords)
    created_or_date = _normalize_text(item.get("created_at") or item.get("start_date") or item.get("end_date"))
    return score, created_or_date


def _select_records(items: list[dict[str, Any]], job_tags: set[str], job_keywords: set[str], limit: int) -> list[dict[str, Any]]:
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for item in items:
        score, sort_key = _best_match_score(item, job_tags, job_keywords)
        item_copy = dict(item)
        item_copy["_score"] = score
        scored.append((score, sort_key, item_copy))
    scored.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    selected = [item for score, _, item in scored if score >= 2]
    if not selected and scored:
        selected = [scored[0][2]]
    return selected[:limit]


def _pick_heading(job: dict[str, Any], job_tags: set[str]) -> str:
    if job_tags and all(tag in NON_TECHNICAL_TAGS for tag in job_tags):
        return "Non-Technical Skills"
    if any(tag in TECHNICAL_TAGS for tag in job_tags):
        return "Technical Skills"
    text = _compile_job_text(job)
    if any(tag in text for tag in NON_TECHNICAL_TAGS):
        return "Non-Technical Skills"
    return "Technical Skills"


def _group_skills(selected_experiences: list[dict[str, Any]], selected_projects: list[dict[str, Any]], job_keywords: list[str]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {
        "Languages": [],
        "Frameworks": [],
        "Databases": [],
        "AI/ML": [],
        "Dev Tools": [],
        "Design": [],
        "Video Editing": [],
        "Animation and Modeling": [],
        "General": [],
    }
    keyword_source: list[str] = []
    for item in selected_experiences + selected_projects:
        keyword_source.extend(item.get("keywords") or [])

    combined = []
    seen: set[str] = set()
    for keyword in keyword_source + job_keywords:
        normalized = _normalize_keyword(keyword)
        if normalized and normalized not in seen:
            seen.add(normalized)
            combined.append(normalized)

    def add(bucket: str, keyword: str) -> None:
        if keyword not in buckets[bucket]:
            buckets[bucket].append(keyword)

    for keyword in combined:
        if keyword in {"python", "javascript", "typescript", "java", "go", "rust", "sql", "kotlin", "swift", "c", "c++", "c#"}:
            add("Languages", keyword)
        elif keyword in {"react", "next", "fastapi", "django", "flask", "langchain", "langgraph", "pandas", "numpy", "tailwind", "shadcn", "express"}:
            add("Frameworks", keyword)
        elif keyword in {"postgresql", "postgres", "mysql", "sqlite", "mongodb", "supabase"}:
            add("Databases", keyword)
        elif keyword in {"ai", "ml", "machine learning", "llm", "groq", "langchain", "langgraph", "prompt engineering"}:
            add("AI/ML", keyword)
        elif keyword in {"git", "docker", "kubernetes", "aws", "ci", "cd", "linux", "bash", "testing", "pytest", "jest"}:
            add("Dev Tools", keyword)
        elif keyword in {"ui", "ux", "figma", "photoshop", "illustrator", "branding"}:
            add("Design", keyword)
        elif keyword in {"premiere", "after effects", "aftereffects", "video", "editing", "final cut"}:
            add("Video Editing", keyword)
        elif keyword in {"blender", "3d", "modeling", "animation"}:
            add("Animation and Modeling", keyword)
        else:
            add("General", keyword)

    return {group: values for group, values in buckets.items() if values}


def _rewrite_experience(exp: dict[str, Any], job: dict[str, Any], job_keywords: list[str]) -> str:
    prompt = (
        "Rewrite this experience for a CV as one concise sentence.\n"
        "Do not invent technologies. Use only the supplied keywords when relevant.\n"
        "Keep it specific and professional.\n"
        f"JOB TITLE: {job.get('title')}\n"
        f"JOB KEYWORDS: {', '.join(job_keywords[:12])}\n"
        f"ROLE: {exp.get('role')} at {exp.get('company')}\n"
        f"ORIGINAL DESCRIPTION: {exp.get('description') or ''}\n"
        f"EXPERIENCE KEYWORDS: {', '.join(exp.get('keywords') or [])}\n"
        "Return only one sentence."
    )
    try:
        result = _call_groq_text(prompt, max_tokens=120)
    except Exception:
        result = ""
    cleaned = result.split("\n")[0].strip().strip('"').strip("'")
    if len(cleaned) < 20:
        return _normalize_text(exp.get("description"))[:220]
    return cleaned[:240]


def _rewrite_project(project: dict[str, Any], job: dict[str, Any], job_keywords: list[str]) -> list[str]:
    prompt = (
        "Rewrite these project bullets for a CV.\n"
        "Return exactly 2 compact bullets, one per line, each starting with '- '.\n"
        "Do not invent technologies.\n"
        f"JOB TITLE: {job.get('title')}\n"
        f"JOB KEYWORDS: {', '.join(job_keywords[:12])}\n"
        f"PROJECT: {project.get('name')}\n"
        f"ORIGINAL DESCRIPTION: {project.get('description') or ''}\n"
        f"PROJECT KEYWORDS: {', '.join(project.get('keywords') or [])}\n"
        "Return only bullets."
    )
    try:
        result = _call_groq_text(prompt, max_tokens=160)
    except Exception:
        result = ""
    bullets: list[str] = []
    for line in result.splitlines():
        line = line.strip()
        if line.startswith("-"):
            line = line[1:].strip()
        if line:
            bullets.append(line[:180])
    if len(bullets) < 2:
        fallback = _normalize_text(project.get("description"))[:180] or f"Built {project.get('name')}."
        return [fallback]
    return bullets[:3]


def _format_date(value: Any) -> str:
    if not value:
        return "Present"
    text = str(value)[:10]
    try:
        return datetime.fromisoformat(text).strftime("%b %Y")
    except Exception:
        return text


def _format_date_range(start: Any, end: Any) -> str:
    return f"{_format_date(start)} -- {_format_date(end)}"


def _render_cv_html(
    profile: dict[str, Any],
    education: list[dict[str, Any]],
    experiences: list[dict[str, Any]],
    projects: list[dict[str, Any]],
    rewritten_exp: dict[str, str],
    rewritten_proj: dict[str, list[str]],
    skills: dict[str, list[str]],
    skills_heading: str,
    job: dict[str, Any],
) -> str:
    template = _jinja_env.get_template("cv_template.html")
    return template.render(
        profile=profile,
        education=education,
        experiences=experiences,
        projects=projects,
        rewritten_exp=rewritten_exp,
        rewritten_proj=rewritten_proj,
        skills=skills,
        skills_heading=skills_heading,
        job=job,
        format_date=_format_date,
        format_date_range=_format_date_range,
    )


def _render_cover_letter_html(profile: dict[str, Any], job: dict[str, Any], body: dict[str, str]) -> str:
    template = _jinja_env.get_template("cover_letter_template.html")
    return template.render(profile=profile, job=job, body=body, today_date=datetime.now().strftime("%B %d, %Y"))


def _compile_html_to_pdf_sync(html_content: str) -> bytes:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html_content, wait_until="domcontentloaded")
        pdf_bytes = page.pdf(
            format="Letter",
            print_background=True,
            margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
        )
        browser.close()
        return pdf_bytes


async def compile_html_to_pdf(html_content: str) -> bytes:
    return await asyncio.to_thread(_compile_html_to_pdf_sync, html_content)


def _storage_path(user_id: str, application_id: str, document_type: str, document_id: str) -> str:
    return f"users/{user_id}/applications/{application_id}/{document_type}/{document_id}.pdf"


def _upload_pdf_to_storage(bucket: str, storage_path: str, pdf_bytes: bytes) -> None:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase storage is not configured.",
        )
    url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{quote(storage_path)}"
    request = Request(
        url,
        data=pdf_bytes,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
            "Content-Type": "application/pdf",
            "x-upsert": "true",
        },
    )
    try:
        with urlopen(request, timeout=60) as response:
            response.read()
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Storage upload failed: {body[:300]}") from exc
    except URLError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Storage upload failed: {exc.reason}") from exc


def _delete_pdf_from_storage(bucket: str, storage_path: str) -> None:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return
    url = f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{quote(storage_path)}"
    request = Request(
        url,
        method="DELETE",
        headers={
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "apikey": settings.supabase_service_role_key,
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            response.read()
    except Exception:
        pass


def _archive_existing_document(connection, application_id: str, document_type: str) -> None:
    existing = fetch_all(
        connection,
        """
        select rendered_storage_bucket, rendered_storage_path
        from generated_documents
        where application_id = %s
          and document_type = %s
          and is_current = true
          and rendered_storage_path is not null
        """,
        (application_id, document_type),
    )
    for row in existing:
        bucket = row.get("rendered_storage_bucket")
        path = row.get("rendered_storage_path")
        if bucket and path:
            _delete_pdf_from_storage(bucket, path)
    execute(
        connection,
        """
        update generated_documents
        set is_current = false,
            generation_status = 'archived',
            updated_at = now()
        where application_id = %s
          and document_type = %s
          and is_current = true
        """,
        (application_id, document_type),
    )


def _save_generated_document(
    connection,
    user_id: str,
    application_id: str,
    job_id: str,
    document_type: str,
    title: str,
    html: str,
    profile_snapshot: dict[str, Any],
    job_snapshot: dict[str, Any],
    generation_params: dict[str, Any],
) -> dict[str, Any]:
    document_id = str(uuid.uuid4())
    cursor = connection.cursor()
    cursor.execute(
        """
        insert into generated_documents (
            document_id,
            user_id,
            job_id,
            application_id,
            document_type,
            title,
            content,
            content_format,
            template_name,
            generation_status,
            source_profile_snapshot,
            source_job_snapshot,
            generation_params,
            provider,
            model_name,
            prompt_version,
            generation_source,
            is_current,
            latest_version_number
        )
        values (
            %s, %s, %s, %s,
            %s, %s, %s, 'html',
            %s, 'draft',
            %s, %s, %s,
            %s, %s, %s,
            'ai', true, 1
        )
        returning document_id
        """,
        (
            document_id,
            user_id,
            job_id,
            application_id,
            document_type,
            title,
            html,
            "jobful-application-v1",
            json.dumps(profile_snapshot),
            json.dumps(job_snapshot),
            json.dumps(generation_params),
            "groq",
            _GROQ_MODEL,
            "v1",
        ),
    )
    connection.commit()
    return {"document_id": document_id}


def _insert_document_version(
    connection,
    document_id: str,
    version_number: int,
    html: str,
    generation_params: dict[str, Any],
) -> str:
    version_id = str(uuid.uuid4())
    with connection.cursor() as cursor:
        cursor.execute(
            """
            insert into document_versions (
                version_id,
                document_id,
                version_number,
                content,
                content_format,
                generation_params,
                provider,
                model_name,
                prompt_version
            ) values (%s, %s, %s, %s, 'html', %s, %s, %s, %s)
            """,
            (
                version_id,
                document_id,
                version_number,
                html,
                json.dumps(generation_params),
                "groq",
                _GROQ_MODEL,
                "v1",
            ),
        )
    connection.commit()
    return version_id


def _set_current_document(connection, application_id: str, document_type: str, document_id: str) -> None:
    column = "current_cv_document_id" if document_type == "cv" else "current_cover_letter_document_id"
    execute(
        connection,
        f"update applications set {column} = %s, updated_at = now() where application_id = %s",
        (document_id, application_id),
    )


def _load_application_bundle(connection, user_id: str, application_id: str) -> dict[str, Any]:
    application = fetch_one(
        connection,
        load_query("applications", "get_application_detail.sql"),
        (application_id, user_id),
    )
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found or not yours")

    documents = fetch_all(
        connection,
        """
        select
          document_id,
          application_id,
          document_type,
          title,
          generation_status,
          is_current,
          content_format,
          content,
          rendered_format,
          rendered_storage_bucket,
          rendered_storage_path,
          rendered_mime_type,
          rendered_file_size_bytes,
          generation_params,
          template_name,
          provider,
          model_name,
          prompt_version,
          created_at,
          updated_at
        from generated_documents
        where application_id = %s
        order by created_at desc
        """,
        (application_id,),
    )
    return {
        "application": _serialize_row(application),
        "documents": [_serialize_row(row) for row in documents],
    }


def get_application_detail(connection, user_id: str, application_id: str) -> dict[str, Any]:
    return _load_application_bundle(connection, user_id, application_id)


def list_application_documents(connection, user_id: str, application_id: str) -> list[dict[str, Any]]:
    bundle = _load_application_bundle(connection, user_id, application_id)
    return bundle["documents"]


def _document_context(connection, user_id: str, application_id: str) -> dict[str, Any]:
    application = fetch_one(
        connection,
        load_query("applications", "get_application_detail.sql"),
        (application_id, user_id),
    )
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found or not yours")

    user = fetch_one(connection, load_query("auth", "get_user_by_id.sql"), (user_id,))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    edu_rows = fetch_all(connection, load_query("cv", "get_user_education.sql"), (user_id,))
    exp_rows = fetch_all(connection, load_query("cv", "get_user_experiences_detail.sql"), (user_id,))
    proj_rows = fetch_all(connection, load_query("cv", "get_user_projects_detail.sql"), (user_id,))

    return {
        "application": _serialize_row(application),
        "user": _serialize_row(user),
        "education": [_serialize_row(row) for row in edu_rows],
        "experiences": [_serialize_row(row) for row in exp_rows],
        "projects": [_serialize_row(row) for row in proj_rows],
    }


def _build_cv_document(connection, user_id: str, application_id: str, document_type: str) -> dict[str, Any]:
    context = _document_context(connection, user_id, application_id)
    application = context["application"]
    user = context["user"]
    job = {
        "job_id": application["job_id"],
        "title": application.get("title") or "",
        "company": application.get("company") or "",
        "description": application.get("description") or "",
        "location": application.get("location") or "",
        "tags": [],
    }
    job_tags = fetch_all(
        connection,
        """
        select ct.tag_name
        from job_tags jt
        join canonical_tags ct on ct.tag_id = jt.tag_id
        where jt.job_id = %s
        order by ct.tag_name
        """,
        (job["job_id"],),
    )
    job["tags"] = [str(row["tag_name"]) for row in job_tags]
    job_keywords = _extract_job_keywords(job)
    job_tag_set = {tag.lower() for tag in job["tags"]}

    experiences = _select_records(context["experiences"], job_tag_set, set(job_keywords), 3)
    projects = _select_records(context["projects"], job_tag_set, set(job_keywords), 4)

    rewritten_exp = {
        str(exp["experience_id"]): _rewrite_experience(exp, job, job_keywords)
        for exp in experiences
    }
    rewritten_proj = {
        str(project["project_id"]): _rewrite_project(project, job, job_keywords)
        for project in projects
    }
    skills = _group_skills(experiences, projects, job_keywords)
    skills_heading = _pick_heading(job, job_tag_set)

    profile = {
        "full_name": user.get("full_name") or "",
        "email": user.get("email") or "",
        "target_role": user.get("raw_job_title") or "",
        "bio": user.get("bio") or "",
        "phone": user.get("phone_number") or "",
        "linkedin": user.get("linkedin_url") or "",
        "github": user.get("github_url") or "",
    }
    profile_snapshot = dict(profile)
    job_snapshot = {
        "job_id": job["job_id"],
        "title": job["title"],
        "company": job["company"],
        "location": job["location"],
        "tags": job["tags"],
        "keywords": job_keywords,
    }
    generation_params = {
        "doc_type": document_type,
        "job_keywords": job_keywords,
        "job_tags": job["tags"],
        "selected_experience_ids": [str(row["experience_id"]) for row in experiences],
        "selected_project_ids": [str(row["project_id"]) for row in projects],
        "excluded_experience_ids": [
            str(row["experience_id"])
            for row in context["experiences"]
            if str(row["experience_id"]) not in {str(item["experience_id"]) for item in experiences}
        ],
        "excluded_project_ids": [
            str(row["project_id"])
            for row in context["projects"]
            if str(row["project_id"]) not in {str(item["project_id"]) for item in projects}
        ],
        "selected_skills": skills,
        "skills_heading": skills_heading,
        "template_name": "jobful-application-v1",
    }

    html = _render_cv_html(
        profile=profile,
        education=context["education"],
        experiences=experiences,
        projects=projects,
        rewritten_exp=rewritten_exp,
        rewritten_proj=rewritten_proj,
        skills=skills,
        skills_heading=skills_heading,
        job=job,
    )

    return {
        "application": application,
        "job": job,
        "profile_snapshot": profile_snapshot,
        "job_snapshot": job_snapshot,
        "selected_experiences": experiences,
        "selected_projects": projects,
        "html": html,
        "generation_params": generation_params,
    }


def _build_cover_letter_document(connection, user_id: str, application_id: str) -> dict[str, Any]:
    context = _document_context(connection, user_id, application_id)
    application = context["application"]
    user = context["user"]
    job = {
        "job_id": application["job_id"],
        "title": application.get("title") or "",
        "company": application.get("company") or "",
        "description": application.get("description") or "",
        "location": application.get("location") or "",
    }
    job_keywords = _extract_job_keywords(job)
    job_tag_rows = fetch_all(
        connection,
        """
        select ct.tag_name
        from job_tags jt
        join canonical_tags ct on ct.tag_id = jt.tag_id
        where jt.job_id = %s
        order by ct.tag_name
        """,
        (job["job_id"],),
    )
    job["tags"] = [str(row["tag_name"]) for row in job_tag_rows]
    selected_experiences = _select_records(context["experiences"], {tag.lower() for tag in job["tags"]}, set(job_keywords), 1)
    selected_projects = _select_records(context["projects"], {tag.lower() for tag in job["tags"]}, set(job_keywords), 1)

    top_exp = selected_experiences[0] if selected_experiences else None
    top_proj = selected_projects[0] if selected_projects else None

    prompt = (
        "Write a concise cover letter in JSON with keys hook, link, proof_1, proof_2, closing.\n"
        f"Candidate: {user.get('full_name')}\n"
        f"Job title: {job.get('title')}\n"
        f"Company: {job.get('company')}\n"
        f"Job keywords: {', '.join(job_keywords[:10])}\n"
        f"Top experience: {top_exp.get('role') if top_exp else ''} {top_exp.get('company') if top_exp else ''} {top_exp.get('description') if top_exp else ''}\n"
        f"Top project: {top_proj.get('name') if top_proj else ''} {top_proj.get('description') if top_proj else ''}\n"
        "Do not use markdown fences."
    )
    body = {
        "hook": "",
        "link": "",
        "proof_1": "",
        "proof_2": "",
        "closing": "",
    }
    try:
        raw = _call_groq_text(prompt, max_tokens=500)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```\s*$", "", cleaned)
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            for key in body:
                value = _normalize_text(parsed.get(key))
                if value:
                    body[key] = value
    except Exception:
        body = {
            "hook": f"{job.get('company')}'s focus on {job_keywords[0] if job_keywords else 'this role'} stood out to me.",
            "link": f"There is a clear parallel with my work on {top_proj.get('name') if top_proj else 'relevant projects'}, where I delivered tangible results.",
            "proof_1": f"I bring experience in {job_keywords[0] if job_keywords else 'engineering'} from {top_exp.get('company') if top_exp else 'prior work'}.",
            "proof_2": f"My recent work shows practical execution across {job_keywords[1] if len(job_keywords) > 1 else 'core skills'}.",
            "closing": f"I would welcome the opportunity to discuss how I can contribute to {job.get('company')}.",
        }

    profile = {
        "full_name": user.get("full_name") or "",
        "email": user.get("email") or "",
        "target_role": user.get("raw_job_title") or "",
        "bio": user.get("bio") or "",
        "phone": user.get("phone_number") or "",
        "linkedin": user.get("linkedin_url") or "",
        "github": user.get("github_url") or "",
    }
    profile_snapshot = dict(profile)
    job_snapshot = {
        "job_id": job["job_id"],
        "title": job["title"],
        "company": job["company"],
        "location": job["location"],
        "keywords": job_keywords,
        "tags": job.get("tags", []),
    }
    generation_params = {
        "doc_type": "cover_letter",
        "job_keywords": job_keywords,
        "job_tags": job.get("tags", []),
        "selected_experience_ids": [str(row["experience_id"]) for row in selected_experiences],
        "selected_project_ids": [str(row["project_id"]) for row in selected_projects],
        "template_name": "jobful-application-v1",
    }
    html = _render_cover_letter_html(profile, job, body)
    return {
        "application": application,
        "job": job,
        "profile_snapshot": profile_snapshot,
        "job_snapshot": job_snapshot,
        "html": html,
        "generation_params": generation_params,
    }


def generate_application_document(connection, user_id: str, application_id: str, document_type: str) -> dict[str, Any]:
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid document type")

    if document_type == "cv":
        document = _build_cv_document(connection, user_id, application_id, document_type)
    else:
        document = _build_cover_letter_document(connection, user_id, application_id)

    application = document["application"]
    _archive_existing_document(connection, application_id, document_type)

    title = f"{'CV' if document_type == 'cv' else 'Cover Letter'} - {application.get('company') or 'Unknown'}"
    saved = _save_generated_document(
        connection,
        user_id,
        application_id,
        application["job_id"],
        document_type,
        title,
        document["html"],
        document["profile_snapshot"],
        document["job_snapshot"],
        document["generation_params"],
    )
    _set_current_document(connection, application_id, document_type, saved["document_id"])

    return {
        "document_id": saved["document_id"],
        "application_id": application_id,
        "document_type": document_type,
        "title": title,
        "html": document["html"],
        "generation_params": document["generation_params"],
        "status": "draft",
    }


def _next_version_number(connection, document_id: str) -> int:
    row = fetch_one(
        connection,
        "select coalesce(max(version_number), 0) as version_number from document_versions where document_id = %s",
        (document_id,),
    )
    return int(row["version_number"] or 0) + 1 if row else 1


def get_compilable_document(
    connection,
    user_id: str,
    application_id: str,
    document_id: str,
    document_type: str,
) -> dict[str, Any]:
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid document type")

    document = fetch_one(
        connection,
        """
        select
          document_id,
          application_id,
          user_id,
          document_type,
          title,
          content,
          generation_params,
          latest_version_number
        from generated_documents
        where document_id = %s and application_id = %s and user_id = %s
        limit 1
        """,
        (document_id, application_id, user_id),
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found or not yours")
    if str(document.get("document_type")) != document_type:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Document type does not match the request")
    return {
        "document_id": document_id,
        "title": document["title"],
        "content": document["content"],
        "generation_params": document.get("generation_params") or {},
    }


def finalize_compiled_document(
    connection,
    user_id: str,
    application_id: str,
    document_id: str,
    document_type: str,
    html: str,
    pdf_bytes: bytes,
) -> dict[str, Any]:
    document = fetch_one(
        connection,
        """
        select document_id, latest_version_number, generation_params, title
        from generated_documents
        where document_id = %s and application_id = %s and user_id = %s
        limit 1
        """,
        (document_id, application_id, user_id),
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found or not yours")

    version_number = _next_version_number(connection, document_id)
    storage_bucket = settings.supabase_storage_bucket
    storage_path = _storage_path(user_id, application_id, document_type, document_id)
    storage_error: str | None = None
    try:
        _upload_pdf_to_storage(storage_bucket, storage_path, pdf_bytes)
    except HTTPException as exc:
        storage_error = str(exc.detail)
        storage_bucket = None
        storage_path = None

    rendered_mime_type = "application/pdf"
    rendered_size = len(pdf_bytes)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            update generated_documents
            set content = %s,
                content_format = 'html',
                rendered_content = %s,
                rendered_format = 'pdf',
                rendered_storage_bucket = %s,
                rendered_storage_path = %s,
                rendered_mime_type = %s,
                rendered_file_size_bytes = %s,
                generation_error = %s,
                generation_status = 'ready',
                is_current = true,
                latest_version_number = %s,
                updated_at = now()
            where document_id = %s and application_id = %s and user_id = %s
            """,
            (
                html,
                html,
                storage_bucket,
                storage_path,
                rendered_mime_type,
                rendered_size,
                storage_error,
                version_number,
                document_id,
                application_id,
                user_id,
            ),
        )

        cursor.execute(
            """
            insert into document_versions (
                document_id,
                version_number,
                content,
                content_format,
                rendered_content,
                rendered_format,
                rendered_storage_bucket,
                rendered_storage_path,
                rendered_mime_type,
                rendered_file_size_bytes,
                generation_error,
                generation_params,
                provider,
                model_name,
                prompt_version
            ) values (
                %s, %s, %s, 'html',
                %s, 'pdf', %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            """,
            (
                document_id,
                version_number,
                html,
                html,
                storage_bucket,
                storage_path,
                rendered_mime_type,
                rendered_size,
                storage_error,
                json.dumps(document.get("generation_params") or {}),
                "groq",
                _GROQ_MODEL,
                "v1",
            ),
        )

        cursor.execute(
            """
            update applications
            set {column} = %s,
                updated_at = now()
            where application_id = %s and user_id = %s
            """.format(column="current_cv_document_id" if document_type == "cv" else "current_cover_letter_document_id"),
            (document_id, application_id, user_id),
        )

    connection.commit()

    return {
        "document_id": document_id,
        "application_id": application_id,
        "document_type": document_type,
        "storage_bucket": storage_bucket,
        "storage_path": storage_path,
        "mime_type": rendered_mime_type,
        "file_size_bytes": rendered_size,
        "version_number": version_number,
    }
