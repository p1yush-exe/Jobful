"""
Two-tier job filtering pipeline.

Tier 0: Cheap algorithmic prefilter — seniority extraction, region blockers,
        skill-token overlap using stemming. Fast, no API cost.

Tier 1: Groq AI gate (job_gate.evaluate_job) on inconclusive jobs only.
        Capped at MAX_AI_CALLS per search to keep latency reasonable.

Entry point: run_filter_pipeline(connection, user_id, raw_jobs, filters)
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from db.executor import fetch_all, fetch_one
from db.query_loader import load_query


# ── tuning constants ──────────────────────────────────────────────────────────

_MAX_AI_CALLS = 8        # Groq calls per search (each ~1-2 s)
_MAX_JOB_AGE_DAYS = 7    # discard listings older than this
_ACCEPT_THRESHOLD = 0.20  # ≥20% skill overlap → algorithmic accept
_SENIORITY_GAP_HARD = 4  # required - user years > this → hard reject


# ── regex patterns ────────────────────────────────────────────────────────────

# "14-17 years", "5+ years of experience", "minimum 10 years", "8 years experience"
_EXP_RANGE = re.compile(
    r"(\d+)\s*[-–]\s*(\d+)\s*\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)",
    re.IGNORECASE,
)
_EXP_PLUS = re.compile(
    r"(\d+)\s*\+\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)",
    re.IGNORECASE,
)
_EXP_MIN = re.compile(
    r"(?:minimum|at\s+least|min\.?|>)\s*(\d+)\s*(?:years?|yrs?)",
    re.IGNORECASE,
)
_EXP_PLAIN = re.compile(
    r"(\d+)\s*(?:years?|yrs?)\s*(?:\+\s*)?(?:of\s+)?(?:relevant\s+|total\s+|industry\s+|work\s+|professional\s+)?(?:experience|exp\b)",
    re.IGNORECASE,
)

# Common western-country explicit locks; non-western users get filtered out
_REGION_BLOCKERS = [
    re.compile(r"(?:must\s+be|only|exclusively)\s+(?:us|uk|eu|canadian|australian)\s+(?:citizen|resident|national|based)", re.IGNORECASE),
    re.compile(r"authoriz(?:ed|ation)\s+to\s+work\s+in\s+(?:the\s+)?(?:us|usa|uk|canada|australia|eu|europe)\b", re.IGNORECASE),
    re.compile(r"(?:us|uk|eu|canada|australia)\s+(?:citizens?\s+only|residents?\s+only|nationals?\s+only)", re.IGNORECASE),
    re.compile(r"no\s+(?:international|overseas|offshore|india|asian)\s+(?:candidates?|applicants?|resumes?)", re.IGNORECASE),
]


# ── text utilities ────────────────────────────────────────────────────────────

def _stem(word: str) -> str:
    """Aggressive but fast suffix stemmer."""
    word = re.sub(r"[^a-z0-9]", "", word.lower())
    if not word:
        return word
    for suffix in ("tion", "ment", "ing", "ed", "er", "or", "ly", "es"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    if len(word) > 4 and word.endswith("s"):
        return word[:-1]
    return word


def _token_set(text: str) -> set[str]:
    return {_stem(t) for t in re.split(r"\W+", text.lower()) if len(t) > 2}


def _skill_overlap(job_text: str, skills: list[str]) -> float:
    """Fraction of user skills matched against job token set."""
    if not skills:
        return 0.0
    job_tokens = _token_set(job_text)
    matched = sum(1 for s in skills if _token_set(s) & job_tokens)
    return matched / len(skills)


def _extract_min_years(text: str) -> int | None:
    """Return lowest explicit years-of-experience requirement, or None."""
    for pattern in (_EXP_RANGE, _EXP_PLUS, _EXP_MIN, _EXP_PLAIN):
        m = pattern.search(text)
        if m:
            nums = [int(g) for g in m.groups() if g is not None]
            return min(nums)
    return None


def _has_region_block(text: str, user_country: str) -> bool:
    # If user is already in a western country, skip check (they pass most locks)
    if user_country.lower() in ("us", "gb", "uk", "ca", "au", "de", "sg"):
        return False
    return any(p.search(text) for p in _REGION_BLOCKERS)


def _age_days(posted_at: str) -> int | None:
    if not posted_at:
        return None
    try:
        dt = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
        return max(0, (datetime.now(timezone.utc) - dt).days)
    except (ValueError, TypeError):
        return None


# ── session truth builder ─────────────────────────────────────────────────────

def build_session_truth(
    connection,
    user_id: str,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Query the DB and assemble a rich user-profile context dict.
    Shape matches what job_gate._build_gate_prompt / _fallback_payload expect.
    """
    f = filters or {}

    user = fetch_one(connection, load_query("auth", "get_user_by_id.sql"), (user_id,))
    if not user:
        return {
            "profile": {"experience_years": -1, "job_title": "", "bio": "", "skills_detected": [], "tags": [], "experiences": [], "projects": []},
            "constraints": {"country": f.get("country", "in"), "salary_min": 0, "employment_type": "", "work_model": ""},
        }

    exp_kw = fetch_all(connection, load_query("cv", "get_user_exp_keywords.sql"), (user_id,))
    proj_kw = fetch_all(connection, load_query("cv", "get_user_proj_keywords.sql"), (user_id,))
    tag_rows = fetch_all(connection, load_query("onboarding", "get_user_selected_tags.sql"), (user_id,))
    exp_rows = fetch_all(connection, load_query("cv", "get_user_experiences_detail.sql"), (user_id,))
    proj_rows = fetch_all(connection, """
        select name, description from user_projects where user_id = %s order by created_at desc
    """, (user_id,))

    skills = list({str(r["keyword"]) for r in exp_kw + proj_kw})
    tags = [str(r["tag_name"]) for r in tag_rows]

    return {
        "profile": {
            "job_title": str(user.get("raw_job_title") or ""),
            "bio": str(user.get("bio") or ""),
            "experience_years": int(user.get("experience_years") or -1),
            "skills_detected": skills,
            "tags": tags,
            "experiences": [
                {
                    "role": str(e.get("role") or ""),
                    "company": str(e.get("company") or ""),
                    "description": str(e.get("description") or ""),
                    "keywords": list(e.get("keywords") or []),
                }
                for e in exp_rows
            ],
            "projects": [
                {"name": str(p.get("name") or ""), "description": str(p.get("description") or "")}
                for p in proj_rows
            ],
        },
        "constraints": {
            "country": f.get("country", "in"),
            "salary_min": int(f.get("salary_min") or 0),
            "employment_type": str(f.get("employment_type") or ""),
            "work_model": str(f.get("work_model") or ""),
        },
    }


# ── tier 0: algorithmic verdict ───────────────────────────────────────────────

_ACCEPT = "accept"
_REJECT = "reject"
_INCONCLUSIVE = "inconclusive"


def _tier0(job: dict[str, Any], session_truth: dict[str, Any]) -> tuple[str, str]:
    """Return (verdict, reason). Cheap, zero API calls."""
    profile = session_truth.get("profile", {})
    constraints = session_truth.get("constraints", {})

    desc = (job.get("description") or "").lower()
    title = (job.get("title") or "").lower()
    combined = f"{title} {desc}"

    user_exp: int = profile.get("experience_years", -1)
    skills: list[str] = profile.get("skills_detected") or []
    country: str = constraints.get("country", "in")

    # 1. Age — discard stale listings
    age = _age_days(job.get("posted_at") or "")
    if age is not None and age > _MAX_JOB_AGE_DAYS:
        return _REJECT, f"Posted {age}d ago (max {_MAX_JOB_AGE_DAYS}d)"

    # 2. Region block
    if _has_region_block(combined, country):
        return _REJECT, "Explicit region restriction"

    # 3. Seniority hard-reject
    min_yrs = _extract_min_years(combined)
    if min_yrs is not None and user_exp >= 0:
        gap = min_yrs - user_exp
        if gap > _SENIORITY_GAP_HARD:
            return _REJECT, f"Requires {min_yrs}+ yrs; user has {user_exp} (gap {gap})"

    # 4. Skill overlap
    score = _skill_overlap(combined, skills)
    if score >= _ACCEPT_THRESHOLD:
        return _ACCEPT, f"{score:.0%} skill overlap"

    return _INCONCLUSIVE, f"{score:.0%} overlap — AI review needed"


# ── enrichment helpers ────────────────────────────────────────────────────────

def _brief(text: str, length: int = 240) -> str:
    text = text.strip()
    return text[:length].rstrip() + ("…" if len(text) > length else "")


def _enrich_algorithmic(job: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        **job,
        "passes_gate": True,
        "brief_description": _brief(job.get("description") or ""),
        "tech_stack": [],
        "why_fit": reason,
        "matching_experiences": [],
        "matching_projects": [],
        "gate_provider": "algorithmic",
    }


# ── full pipeline ─────────────────────────────────────────────────────────────

def run_filter_pipeline(
    connection,
    user_id: str,
    raw_jobs: list[dict[str, Any]],
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    1. Build session_truth from DB.
    2. Run Tier 0 on every raw job (fast, no API).
    3. Run Tier 1 Groq gate on inconclusive jobs (capped at MAX_AI_CALLS).
    4. Return enriched passing jobs, sorted most-recent first.
    """
    session_truth = build_session_truth(connection, user_id, filters)
    skills = session_truth.get("profile", {}).get("skills_detected") or []

    accepted: list[dict[str, Any]] = []
    inconclusive: list[dict[str, Any]] = []

    for job in raw_jobs:
        verdict, reason = _tier0(job, session_truth)
        if verdict == _ACCEPT:
            accepted.append(_enrich_algorithmic(job, reason))
        elif verdict == _REJECT:
            pass
        else:
            inconclusive.append((job, reason))

    # Tier 1: AI gate on inconclusive, spend remaining budget
    ai_budget = max(0, _MAX_AI_CALLS - len(accepted))
    if ai_budget > 0 and inconclusive and skills:
        from services.job_gate import evaluate_job  # local import avoids circular at module load
        for job, t0_reason in inconclusive[:ai_budget]:
            try:
                result = evaluate_job(session_truth, job)
                ev = result.get("evaluation") or {}
                if ev.get("passes_filters"):
                    ext = result.get("extracted_job_data") or {}
                    fit = result.get("fit_analysis") or {}
                    accepted.append({
                        **job,
                        "passes_gate": True,
                        "brief_description": ext.get("brief_description") or _brief(job.get("description") or ""),
                        "tech_stack": ext.get("tech_stack") or [],
                        "why_fit": fit.get("why_fit") or t0_reason,
                        "matching_experiences": fit.get("matching_experiences") or [],
                        "matching_projects": fit.get("matching_projects") or [],
                        "gate_provider": result.get("llm_provider") or "ai",
                    })
            except Exception:
                # AI unavailable — pass job with minimal enrichment rather than losing it
                accepted.append(_enrich_algorithmic(job, t0_reason))
    elif ai_budget > 0 and inconclusive:
        # No skills in profile yet — include inconclusive jobs so search isn't empty
        for job, reason in inconclusive:
            accepted.append(_enrich_algorithmic(job, reason))

    accepted.sort(key=lambda j: j.get("posted_at") or "", reverse=True)
    return accepted
