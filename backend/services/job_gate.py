"""AI-based job evaluation gate.

Each raw job is evaluated against the user's session_truth (profile, constraints,
experience summary). Groq is primary; HuggingFace Inference API is the fallback;
a pure-heuristic extractor is used when both LLMs fail.

Not yet wired into a route — ready to integrate into the sourcing/search pipeline.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from services.groq_client import GroqClientError, call_groq_json
from services.hf_fallback_client import HFFallbackError, call_hf_json


OUTPUT_SCHEMA = {
    "evaluation": {
        "passes_filters": False,
        "rejection_reason": None,
    },
    "extracted_job_data": {
        "job_title": "string",
        "company_name": "string",
        "location": "string",
        "hiring_type": "string",
        "compensation": "string",
        "brief_description": "string",
        "tech_stack": [],
        "work_model": "string",
    },
    "fit_analysis": {
        "matching_experiences": [],
        "matching_projects": [],
        "why_fit": "string",
    },
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _extract_hiring_type(text: str) -> str:
    lowered = text.lower()
    if "contract" in lowered:
        return "Contract"
    if "part-time" in lowered or "part time" in lowered:
        return "Part-Time"
    if "intern" in lowered:
        return "Internship"
    if "temporary" in lowered:
        return "Temporary"
    return "Full-Time"


def _extract_work_model(text: str, location: str) -> str:
    lowered = f"{text} {location}".lower()
    if "hybrid" in lowered:
        return "Hybrid"
    if "remote" in lowered or "distributed" in lowered:
        return "Remote"
    if "onsite" in lowered or "on-site" in lowered:
        return "Onsite"
    return "Not specified"


def _salary_text(job: dict[str, Any]) -> str:
    currency = _clean(job.get("currency", ""))
    minimum = job.get("salary_min")
    maximum = job.get("salary_max")
    if minimum is None and maximum is None:
        return job.get("salary_range") or "Not specified"
    if minimum is not None and maximum is not None:
        return f"{currency} {minimum:g} - {maximum:g}".strip()
    value = minimum if minimum is not None else maximum
    return f"{currency} {value:g}".strip()


def _fallback_payload(session_truth: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    description = _clean(job.get("description"))
    brief = description[:220] + ("..." if len(description) > 220 else "")
    # support both nested profile.skills_detected and flat skills key
    profile = session_truth.get("profile") or {}
    skills = profile.get("skills_detected") or session_truth.get("skills") or []
    lowered = description.lower()
    matched_skills = [skill for skill in skills if skill.lower() in lowered][:6]
    return {
        "evaluation": {"passes_filters": True, "rejection_reason": None},
        "extracted_job_data": {
            "job_title": _clean(job.get("title")) or "Unknown role",
            "company_name": _clean(job.get("company")) or "Unknown company",
            "location": _clean(job.get("location")) or "Not specified",
            "hiring_type": _extract_hiring_type(description),
            "compensation": _salary_text(job),
            "brief_description": brief or "No description provided.",
            "tech_stack": matched_skills,
            "work_model": _extract_work_model(description, _clean(job.get("location"))),
        },
        "fit_analysis": {
            "matching_experiences": matched_skills[:3],
            "matching_projects": matched_skills[3:6],
            "why_fit": "This role aligns with your background and keyword overlap.",
        },
    }


def _build_gate_prompt(session_truth: dict[str, Any], job: dict[str, Any]) -> str:
    return (
        "You are an expert job-filtering engine and structured data extractor.\n"
        "Evaluate the raw job against the user's constraints from SESSION_TRUTH.\n"
        "Step 1: Strict filtering. Reject if the description explicitly blocks the user's region, pay floor, experience level, or education level.\n"
        "Step 2: If the job passes, extract concise UI-ready fields.\n"
        "Rules:\n"
        "- Return ONLY valid JSON matching JSON_SCHEMA.\n"
        "- Keep brief_description to 1-2 concise sentences.\n"
        "- If rejected: set extracted_job_data and fit_analysis to null.\n"
        "- Prefer concrete rejection reasons: region restriction, seniority mismatch, pay mismatch, education requirement.\n"
        f"JSON_SCHEMA:\n{json.dumps(OUTPUT_SCHEMA, ensure_ascii=False)}\n"
        f"SESSION_TRUTH:\n{json.dumps(session_truth, ensure_ascii=False)}\n"
        f"JOB:\n{json.dumps(job, ensure_ascii=False)}\n"
    )


def _normalize_string_list(value: Any, limit: int = 6) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        cleaned = _clean(item)
        if cleaned:
            result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _validate_gate_payload(payload: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    evaluation = payload.get("evaluation") if isinstance(payload.get("evaluation"), dict) else {}
    extracted = payload.get("extracted_job_data")
    fit = payload.get("fit_analysis")

    passes = bool(evaluation.get("passes_filters"))
    rejection_reason = _clean(evaluation.get("rejection_reason")) or None

    if not passes:
        return {
            "evaluation": {"passes_filters": False, "rejection_reason": rejection_reason or "Rejected by eligibility filter."},
            "extracted_job_data": None,
            "fit_analysis": None,
        }

    if not isinstance(extracted, dict):
        extracted = fallback["extracted_job_data"]
    if not isinstance(fit, dict):
        fit = fallback["fit_analysis"]

    return {
        "evaluation": {"passes_filters": True, "rejection_reason": None},
        "extracted_job_data": {
            "job_title": _clean(extracted.get("job_title")) or fallback["extracted_job_data"]["job_title"],
            "company_name": _clean(extracted.get("company_name")) or fallback["extracted_job_data"]["company_name"],
            "location": _clean(extracted.get("location")) or fallback["extracted_job_data"]["location"],
            "hiring_type": _clean(extracted.get("hiring_type")) or fallback["extracted_job_data"]["hiring_type"],
            "compensation": _clean(extracted.get("compensation")) or fallback["extracted_job_data"]["compensation"],
            "brief_description": _clean(extracted.get("brief_description")) or fallback["extracted_job_data"]["brief_description"],
            "tech_stack": _normalize_string_list(extracted.get("tech_stack")) or fallback["extracted_job_data"]["tech_stack"],
            "work_model": _clean(extracted.get("work_model")) or fallback["extracted_job_data"]["work_model"],
        },
        "fit_analysis": {
            "matching_experiences": _normalize_string_list(fit.get("matching_experiences")),
            "matching_projects": _normalize_string_list(fit.get("matching_projects")),
            "why_fit": _clean(fit.get("why_fit")) or fallback["fit_analysis"]["why_fit"],
        },
    }


def evaluate_job(session_truth: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one raw job dict against user session_truth. Returns gate payload dict."""
    fallback = _fallback_payload(session_truth, job)
    prompt = _build_gate_prompt(session_truth, job)
    provider = "groq"
    error = ""
    try:
        raw = call_groq_json(prompt)
    except GroqClientError as exc:
        error = str(exc)
        try:
            raw = call_hf_json(prompt)
            provider = "ai"
        except HFFallbackError as hf_exc:
            result = fallback
            result["evaluation"]["passes_filters"] = True
            result["llm_provider"] = "algorithmic"
            result["gate_error"] = ""
            result["evaluated_at"] = datetime.now(timezone.utc).isoformat()
            return result

    result = _validate_gate_payload(raw, fallback)
    result["llm_provider"] = provider
    result["gate_error"] = ""
    result["evaluated_at"] = datetime.now(timezone.utc).isoformat()
    return result
