import re

from fastapi import HTTPException, status

from api.schemas.onboarding import OnboardingStateResponse, ProfileUpdateRequest, SelectedTagsRequest, TagResponse
from db.executor import execute, fetch_all, fetch_one
from db.query_loader import load_query


_TAG_SYNONYMS: dict[str, list[str]] = {
    "frontend": ["front end", "front-end", "ui", "web", "web app"],
    "backend": ["back end", "back-end", "server", "api"],
    "fullstack": ["full stack", "full-stack"],
    "mobile": ["mobile", "mobile dev", "mobile development"],
    "embedded-systems": ["embedded", "firmware", "microcontroller"],
    "systems-programming": ["systems programming", "low level", "kernel", "os"],
    "devops": ["devops", "sre", "site reliability", "infrastructure"],
    "cloud": ["cloud", "aws", "gcp", "azure"],
    "security": ["security", "cybersecurity", "infosec", "appsec"],
    "testing": ["testing", "qa", "quality assurance"],
    "software development": ["software development", "software engineering", "software engineer", "developer", "engineering"],
    "ai-ml": ["ai", "machine learning", "ml", "deep learning", "dl", "nlp", "computer vision", "cv", "llm", "gen ai", "generative ai"],
    "data-science": ["data science", "analytics", "statistics", "modelling", "modeling"],
    "data-engineering": ["data engineering", "data engineer", "etl", "pipeline", "data pipelines", "warehouse", "data warehouse"],
    "research": ["research", "r&d", "researcher", "scientist"],
    "automation": ["automation", "scripting", "rpa", "workflow"],
    "product-management": ["product manager", "product management", "pm", "product owner", "product lead"],
    "consulting": ["consulting", "consultant", "advisory"],
    "technical-writing": ["technical writing", "documentation", "tech writer"],
    "agile": ["agile", "scrum", "kanban"],
    "ui-ux": ["ui/ux", "ui ux", "user experience", "ux", "ui", "interaction design"],
    "product-design": ["product design", "ux design", "design lead"],
    "graphic-design": ["graphic design", "visual design", "branding", "brand design"],
    "motion-design": ["motion design", "animation", "motion graphics", "vfx"],
    "video-editing": ["video editing", "editor", "post production", "color grading", "colour grading"],
    "content-creation": ["content creation", "copywriting", "copywriter", "social media", "blogging"],
    "photography": ["photography", "photographer"],
    "3d-modelling": ["3d", "3d modeling", "3d modelling", "cad", "rendering", "sculpting"],
    "game-development": ["game development", "game dev", "gaming"],
    "ar-vr": ["ar", "vr", "xr", "augmented reality", "virtual reality", "spatial computing"],
    "robotics": ["robotics", "ros", "mechatronics"],
    "blockchain": ["blockchain", "web3", "smart contract", "crypto", "defi"],
    "ios": ["ios", "iphone", "swift"],
    "android": ["android", "kotlin"],
    "electronics": ["electronics", "pcb", "fpga", "circuit design"],
    "biotech": ["biotech", "bioinformatics", "computational biology"],
    "fintech": ["fintech", "payments", "trading", "regtech"],
    "sales-growth": ["sales", "growth", "biz dev", "business development", "gtm", "go to market", "marketing"],
    "operations": ["operations", "ops", "supply chain", "logistics"],
    "hr-people": ["hr", "people ops", "recruiting", "talent", "human resources", "l&d", "learning and development"],
    "legal-compliance": ["legal", "compliance", "regulatory", "risk", "policy"],
}


def _normalize_tag_name(tag_name: str) -> str:
    return tag_name.strip().lower()


def _normalize_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _stem_token(token: str) -> str:
    if len(token) <= 3:
        return token
    if token.endswith("ies") and len(token) > 4:
        return f"{token[:-3]}y"
    for suffix in ("ing", "ed", "er", "or", "ly", "es"):
        if len(token) > len(suffix) + 2 and token.endswith(suffix):
            return token[: -len(suffix)]
    if token.endswith("s") and len(token) > 4:
        return token[:-1]
    return token


def _extract_terms(text: str) -> tuple[set[str], set[str], set[str]]:
    normalized = _normalize_text(text)
    if not normalized:
        return set(), set(), set()
    tokens = normalized.split()
    token_set = set(tokens)
    stem_set = {_stem_token(token) for token in tokens}
    phrases: set[str] = set()
    for size in (2, 3):
        for index in range(len(tokens) - size + 1):
            phrases.add(" ".join(tokens[index : index + size]))
    return token_set, stem_set, phrases


def _phrase_matches(phrase: str, token_set: set[str], stem_set: set[str], phrases: set[str]) -> bool:
    normalized = _normalize_text(phrase)
    if not normalized:
        return False
    if normalized in phrases or normalized in token_set:
        return True
    phrase_tokens = normalized.split()
    return all(_stem_token(token) in stem_set for token in phrase_tokens)


def _recommend_tag_names(raw_job_title: str, bio: str | None, canonical_tag_names: list[str]) -> list[str]:
    combined_text = " ".join(part for part in [raw_job_title, bio or ""] if part)
    token_set, stem_set, phrases = _extract_terms(combined_text)
    matched: list[str] = []
    for tag_name in canonical_tag_names:
        tag_phrase = _normalize_text(tag_name.replace("-", " "))
        tag_matches = _phrase_matches(tag_phrase, token_set, stem_set, phrases)
        if not tag_matches:
            for synonym in _TAG_SYNONYMS.get(tag_name, []):
                if _phrase_matches(synonym, token_set, stem_set, phrases):
                    tag_matches = True
                    break
        if tag_matches:
            matched.append(tag_name)
    return matched


def _tag_response(row: dict[str, object]) -> TagResponse:
    return TagResponse(tag_id=row["tag_id"], tag_name=str(row["tag_name"]))


def _load_canonical_tags(connection) -> list[dict[str, object]]:
    return fetch_all(connection, load_query("onboarding", "get_canonical_tags.sql"), ())


def _recommended_tags_for_user(connection, raw_job_title: str, bio: str | None) -> list[TagResponse]:
    canonical_tags = _load_canonical_tags(connection)
    canonical_names = [str(row["tag_name"]) for row in canonical_tags]
    recommended_names = set(_recommend_tag_names(raw_job_title, bio, canonical_names))
    return [_tag_response(row) for row in canonical_tags if str(row["tag_name"]) in recommended_names]


def _get_user_tags(connection, query_name: str, user_id: str) -> list[TagResponse]:
    rows = fetch_all(connection, load_query("onboarding", query_name), (user_id,))
    return [_tag_response(row) for row in rows]


def get_onboarding_state(connection, user_id: str) -> OnboardingStateResponse:
    user = fetch_one(connection, load_query("auth", "get_user_by_id.sql"), (user_id,))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    recommended = _recommended_tags_for_user(connection, str(user.get("raw_job_title") or ""), user.get("bio"))
    assigned = _get_user_tags(connection, "get_user_assigned_tags.sql", user_id)
    if not assigned:
        # Keep onboarding resilient for fresh users: ensure canonical tags are always available.
        canonical_tags = _load_canonical_tags(connection)
        for row in canonical_tags:
            execute(connection, load_query("onboarding", "insert_user_assigned_tag.sql"), (user_id, row["tag_id"]))
        assigned = _get_user_tags(connection, "get_user_assigned_tags.sql", user_id)
    selected = _get_user_tags(connection, "get_user_selected_tags.sql", user_id)
    return OnboardingStateResponse(
        user_id=str(user["user_id"]),
        raw_job_title=str(user.get("raw_job_title") or ""),
        bio=user.get("bio"),
        recommended_tags=recommended,
        assigned_tags=assigned,
        selected_tags=selected,
    )


def update_profile_and_recommend_tags(connection, user_id: str, payload: ProfileUpdateRequest) -> OnboardingStateResponse:
    updated_user = fetch_one(
        connection,
        load_query("onboarding", "update_user_profile.sql"),
        (payload.raw_job_title, payload.bio, user_id),
    )
    if updated_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    canonical_tags = _load_canonical_tags(connection)
    execute(connection, load_query("onboarding", "clear_user_assigned_tags.sql"), (user_id,))
    execute(connection, load_query("onboarding", "clear_user_selected_tags.sql"), (user_id,))
    for row in canonical_tags:
        execute(connection, load_query("onboarding", "insert_user_assigned_tag.sql"), (user_id, row["tag_id"]))

    return get_onboarding_state(connection, user_id)


def set_selected_tags(connection, user_id: str, payload: SelectedTagsRequest) -> OnboardingStateResponse:
    # dedupe while preserving order
    seen: set = set()
    selected_tag_ids: list = []
    for tag_id in payload.tag_ids:
        if tag_id not in seen:
            seen.add(tag_id)
            selected_tag_ids.append(tag_id)

    if not selected_tag_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Select at least one tag")

    # ensure all canonical tags are in user_assigned_tags so any can be selected
    canonical_tags = _load_canonical_tags(connection)
    for row in canonical_tags:
        execute(connection, load_query("onboarding", "insert_user_assigned_tag.sql"), (user_id, row["tag_id"]))

    execute(connection, load_query("onboarding", "clear_user_selected_tags.sql"), (user_id,))
    for tag_id in selected_tag_ids:
        execute(connection, load_query("onboarding", "insert_user_selected_tag.sql"), (user_id, str(tag_id)))

    return get_onboarding_state(connection, user_id)


def get_eligible_jobs(connection, user_id: str) -> list[dict[str, object]]:
    return fetch_all(connection, load_query("jobs", "get_eligible_jobs.sql"), (user_id,))
