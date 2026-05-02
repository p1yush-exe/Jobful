from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException, status

from core.config import settings


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _http_get_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    req = Request(url, headers=headers or {})
    try:
        with urlopen(req, timeout=30) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return json.loads(resp.read().decode(charset))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Search API error {exc.code}: {body[:300]}",
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Search API unreachable: {exc.reason}",
        ) from exc


def _salary_range(salary_min: float | None, salary_max: float | None, currency: str) -> str | None:
    if salary_min is None and salary_max is None:
        return None
    parts = [str(int(v)) for v in [salary_min, salary_max] if v is not None]
    result = " – ".join(parts)
    if currency:
        result += f" {currency.upper()}"
    return result


# employment_type values for JSearch: FULLTIME, PARTTIME, CONTRACTOR, INTERN
# date_posted values for JSearch: all, today, 3days, week, month
def fetch_jsearch(
    query: str,
    location: str,
    country: str,
    pages: int,
    delay: float,
    employment_types: str = "",
    date_posted: str = "month",
    work_from_home: bool = False,
) -> list[dict[str, Any]]:
    if not settings.rapidapi_key:
        return []

    headers = {
        "X-RapidAPI-Key": settings.rapidapi_key,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
    }
    fetched_at = datetime.now(timezone.utc).isoformat()
    jobs: list[dict[str, Any]] = []

    for page in range(1, pages + 1):
        params: dict[str, Any] = {
            "query": f"{query} in {location}" if location else query,
            "page": page,
            "num_pages": 1,
            "country": country.lower(),
            "date_posted": date_posted or "month",
        }
        if employment_types:
            params["employment_types"] = employment_types
        if work_from_home:
            params["work_from_home"] = "true"

        url = f"https://jsearch.p.rapidapi.com/search?{urlencode(params)}"
        payload = _http_get_json(url, headers=headers)

        for item in payload.get("data", []):
            city = _clean(item.get("job_city"))
            state = _clean(item.get("job_state"))
            ctry = _clean(item.get("job_country") or country)
            loc = ", ".join(p for p in [city, state, ctry] if p)
            salary_min = _float(item.get("job_min_salary"))
            salary_max = _float(item.get("job_max_salary"))
            currency = _clean(item.get("job_salary_currency"))

            jobs.append({
                "source": "jsearch",
                "external_id": _clean(item.get("job_id")),
                "title": _clean(item.get("job_title")),
                "company": _clean(item.get("employer_name")),
                "location": loc,
                "country": country.lower(),
                "description": _clean(item.get("job_description")),
                "apply_url": _clean(item.get("job_apply_link")),
                "source_url": _clean(item.get("job_google_link")),
                "salary_range": _salary_range(salary_min, salary_max, currency),
                "salary_min_raw": salary_min,
                "employment_type": _clean(item.get("job_employment_type")),
                "work_model": "Remote" if item.get("job_is_remote") else _clean(item.get("job_city") and "On-site" or ""),
                "posted_at": _clean(item.get("job_posted_at_datetime_utc") or ""),
                "fetched_at": fetched_at,
            })

        if page < pages:
            time.sleep(delay)

    return jobs


def fetch_adzuna(
    query: str,
    location: str,
    country: str,
    pages: int,
    delay: float,
    employment_type: str = "",
    salary_min: int = 0,
    work_model: str = "",
) -> list[dict[str, Any]]:
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        return []

    fetched_at = datetime.now(timezone.utc).isoformat()
    jobs: list[dict[str, Any]] = []

    for page in range(1, pages + 1):
        params: dict[str, Any] = {
            "app_id": settings.adzuna_app_id,
            "app_key": settings.adzuna_app_key,
            "results_per_page": 20,
            "what": query,
            "where": location,
            "content-type": "application/json",
        }
        if salary_min > 0:
            params["salary_min"] = salary_min
        if employment_type == "FULLTIME":
            params["full_time"] = "1"
        elif employment_type == "PARTTIME":
            params["part_time"] = "1"
        elif employment_type == "CONTRACTOR":
            params["contract"] = "1"
        if work_model.lower() == "remote":
            params["where"] = "remote"

        url = f"https://api.adzuna.com/v1/api/jobs/{country.lower()}/search/{page}?{urlencode(params)}"
        payload = _http_get_json(url)

        for item in payload.get("results", []):
            def _nested(path: list[str]) -> str:
                cur: Any = item
                for k in path:
                    if not isinstance(cur, dict):
                        return ""
                    cur = cur.get(k)
                return _clean(cur)

            smin = _float(item.get("salary_min"))
            smax = _float(item.get("salary_max"))
            currency = _clean(item.get("salary_currency"))

            jobs.append({
                "source": "adzuna",
                "external_id": _clean(item.get("id")),
                "title": _clean(item.get("title")),
                "company": _nested(["company", "display_name"]),
                "location": _nested(["location", "display_name"]),
                "country": country.lower(),
                "description": _clean(item.get("description")),
                "apply_url": _clean(item.get("redirect_url")),
                "source_url": _clean(item.get("adref")),
                "salary_range": _salary_range(smin, smax, currency),
                "salary_min_raw": smin,
                "employment_type": employment_type or "",
                "work_model": work_model or "",
                "posted_at": _clean(item.get("created") or ""),
                "fetched_at": fetched_at,
            })

        if page < pages:
            time.sleep(delay)

    return jobs


def _dedupe(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for job in jobs:
        key = (
            job["source"],
            re.sub(r"[^a-z0-9]", "", (job["external_id"] or job["apply_url"] or job["title"]).lower()),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(job)
    return out


def search_jobs(
    query: str,
    location: str = "",
    country: str = "in",
    source: str = "all",
    employment_type: str = "",   # FULLTIME, PARTTIME, CONTRACTOR, INTERN
    work_model: str = "",        # remote, hybrid, onsite
    date_posted: str = "month",  # today, 3days, week, month
    salary_min: int = 0,
    allow_unspecified_pay: bool = True,
) -> list[dict[str, Any]]:
    """Live search — never writes to DB."""
    pages = settings.job_search_pages
    delay = settings.job_search_delay
    work_from_home = work_model.lower() == "remote"

    all_jobs: list[dict[str, Any]] = []

    if source in ("jsearch", "all"):
        all_jobs.extend(fetch_jsearch(
            query, location, country, pages, delay,
            employment_types=employment_type,
            date_posted=date_posted,
            work_from_home=work_from_home,
        ))

    if source in ("adzuna", "all"):
        all_jobs.extend(fetch_adzuna(
            query, location, country, pages, delay,
            employment_type=employment_type,
            salary_min=salary_min,
            work_model=work_model,
        ))

    jobs = _dedupe(all_jobs)

    # filter by min salary if set and pay is specified
    if salary_min > 0:
        filtered = []
        for j in jobs:
            raw = j.get("salary_min_raw")
            if raw is None:
                if allow_unspecified_pay:
                    filtered.append(j)
            elif raw >= salary_min:
                filtered.append(j)
        jobs = filtered

    return jobs
