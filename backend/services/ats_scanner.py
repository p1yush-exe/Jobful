from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from services.job_feed_utils import Job, clean_text, dedupe_jobs, export_jobs


DEFAULT_PORTALS_PATH = Path(__file__).resolve().parents[1] / "data" / "ats_portals.json"


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower())
    return cleaned.strip("-")


def detect_api(company: dict[str, Any]) -> tuple[str, str, str] | None:
    explicit_api = clean_text(company.get("api"))
    if explicit_api and "greenhouse" in explicit_api:
        match = re.search(r"boards-api\.greenhouse\.io/v1/boards/([^/?#]+)/jobs", explicit_api)
        slug = match.group(1) if match else slugify(company.get("name", ""))
        return "greenhouse", explicit_api, slug

    careers_url = clean_text(company.get("careers_url"))
    ashby_match = re.search(r"jobs\.ashbyhq\.com/([^/?#]+)", careers_url)
    if ashby_match:
        slug = ashby_match.group(1)
        return "ashby", f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true", slug

    lever_match = re.search(r"jobs\.lever\.co/([^/?#]+)", careers_url)
    if lever_match:
        slug = lever_match.group(1)
        return "lever", f"https://api.lever.co/v0/postings/{slug}", slug

    greenhouse_match = re.search(r"(?:boards|job-boards(?:\.eu)?)\.greenhouse\.io/([^/?#]+)", careers_url)
    if greenhouse_match:
        slug = greenhouse_match.group(1)
        return "greenhouse", f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true", slug
    return None


def _normalize_posted_at(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000.0
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    text = str(value).strip()
    if text.isdigit():
        timestamp = float(text)
        if timestamp > 10_000_000_000:
            timestamp = timestamp / 1000.0
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except ValueError:
        return text


def _freshness_days(posted_at: str) -> int | None:
    if not posted_at:
        return None
    try:
        parsed = datetime.fromisoformat(posted_at.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
    delta = datetime.now(timezone.utc) - parsed
    return max(0, int(delta.days))


def build_title_filter(config: dict[str, Any]) -> tuple[list[str], list[str]]:
    title_filter = config.get("title_filter") or {}
    positive = [clean_text(v).lower() for v in title_filter.get("positive", []) if clean_text(v)]
    negative = [clean_text(v).lower() for v in title_filter.get("negative", []) if clean_text(v)]
    return positive, negative


def title_is_allowed(title: str, positive: list[str], negative: list[str]) -> bool:
    lowered = title.lower()
    pos_ok = (not positive) or any(p in lowered for p in positive)
    neg_hit = any(n in lowered for n in negative)
    return pos_ok and not neg_hit


def http_get_json(url: str, timeout: int = 20) -> dict[str, Any] | list[Any]:
    request = Request(url, headers={"User-Agent": "applybot-tracker/ats-scanner"})
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {body[:400]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error for {url}: {exc.reason}") from exc


def parse_greenhouse(payload: dict[str, Any], company: str, fetched_at: str, ats_slug: str) -> list[Job]:
    jobs = []
    for item in payload.get("jobs", []):
        posted_at = _normalize_posted_at(item.get("updated_at") or item.get("first_published"))
        jobs.append(
            Job(
                source="ats_greenhouse",
                external_id=clean_text(item.get("id")),
                title=clean_text(item.get("title")),
                company=company,
                location=clean_text((item.get("location") or {}).get("name")),
                country="",
                description=clean_text(item.get("content")),
                apply_url=clean_text(item.get("absolute_url")),
                source_url=clean_text(item.get("absolute_url")),
                publisher="Greenhouse",
                salary_min=None,
                salary_max=None,
                currency="",
                posted_at=posted_at,
                fetched_at=fetched_at,
                raw_payload=item,
                ats_type="greenhouse",
                ats_company_slug=ats_slug,
                job_freshness_days=_freshness_days(posted_at),
            )
        )
    return jobs


def parse_ashby(payload: dict[str, Any], company: str, fetched_at: str, ats_slug: str) -> list[Job]:
    jobs = []
    for item in payload.get("jobs", []):
        compensation = item.get("compensation") or {}
        posted_at = _normalize_posted_at(item.get("publishedDate"))
        jobs.append(
            Job(
                source="ats_ashby",
                external_id=clean_text(item.get("id")),
                title=clean_text(item.get("title")),
                company=company,
                location=clean_text(item.get("location")),
                country="",
                description=clean_text(item.get("descriptionPlain") or item.get("descriptionHtml")),
                apply_url=clean_text(item.get("jobUrl")),
                source_url=clean_text(item.get("jobUrl")),
                publisher="Ashby",
                salary_min=compensation.get("minCompensation"),
                salary_max=compensation.get("maxCompensation"),
                currency=clean_text(compensation.get("currencyCode")),
                posted_at=posted_at,
                fetched_at=fetched_at,
                raw_payload=item,
                ats_type="ashby",
                ats_company_slug=ats_slug,
                job_freshness_days=_freshness_days(posted_at),
            )
        )
    return jobs


def parse_lever(payload: list[Any], company: str, fetched_at: str, ats_slug: str) -> list[Job]:
    jobs = []
    for item in payload:
        categories = item.get("categories") or {}
        posted_at = _normalize_posted_at(item.get("createdAt"))
        jobs.append(
            Job(
                source="ats_lever",
                external_id=clean_text(item.get("id")),
                title=clean_text(item.get("text")),
                company=company,
                location=clean_text(categories.get("location")),
                country="",
                description=clean_text(item.get("descriptionPlain") or item.get("description")),
                apply_url=clean_text(item.get("hostedUrl")),
                source_url=clean_text(item.get("hostedUrl")),
                publisher="Lever",
                salary_min=None,
                salary_max=None,
                currency="",
                posted_at=posted_at,
                fetched_at=fetched_at,
                raw_payload=item,
                ats_type="lever",
                ats_company_slug=ats_slug,
                job_freshness_days=_freshness_days(posted_at),
            )
        )
    return jobs


async def scan_company(company: dict[str, Any], positive: list[str], negative: list[str]) -> tuple[list[Job], str | None]:
    api_info = detect_api(company)
    if not api_info:
        return [], f"{company.get('name', 'unknown')}: no supported ATS detected"

    source_type, url, ats_slug = api_info
    fetched_at = datetime.now(timezone.utc).isoformat()

    try:
        payload = await asyncio.to_thread(http_get_json, url)
        if source_type == "greenhouse":
            jobs = parse_greenhouse(
                payload if isinstance(payload, dict) else {},
                clean_text(company.get("name")),
                fetched_at,
                ats_slug,
            )
        elif source_type == "ashby":
            jobs = parse_ashby(
                payload if isinstance(payload, dict) else {},
                clean_text(company.get("name")),
                fetched_at,
                ats_slug,
            )
        else:
            jobs = parse_lever(
                payload if isinstance(payload, list) else [],
                clean_text(company.get("name")),
                fetched_at,
                ats_slug,
            )
        filtered = [job for job in jobs if title_is_allowed(job.title, positive, negative)]
        return filtered, None
    except Exception as exc:  # noqa: BLE001
        return [], f"{company.get('name', 'unknown')}: {exc}"


def load_portals(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Portals file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("Portals file must contain a JSON object.")
    return data


async def run_scan(portals_path: Path, limit: int, output_dir: Path) -> dict[str, Any]:
    config = load_portals(portals_path)
    positive, negative = build_title_filter(config)
    companies = [company for company in (config.get("tracked_companies") or []) if company.get("enabled", True)]
    if limit > 0:
        companies = companies[:limit]

    results = await asyncio.gather(*(scan_company(company, positive, negative) for company in companies))

    jobs: list[Job] = []
    errors: list[str] = []
    for company_jobs, err in results:
        jobs.extend(company_jobs)
        if err:
            errors.append(err)

    unique_jobs = dedupe_jobs(jobs)
    export_jobs(unique_jobs, output_dir)
    return {
        "companies_considered": len(companies),
        "jobs_before_dedupe": len(jobs),
        "jobs_after_dedupe": len(unique_jobs),
        "errors": errors,
        "output_dir": str(output_dir.resolve()),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan jobs directly from ATS company boards.")
    parser.add_argument("--portals", default=str(DEFAULT_PORTALS_PATH), help="Path to ATS portals JSON config.")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of companies. 0 scans all.")
    parser.add_argument("--output", default="exports/ats", help="Output folder for ATS jobs export.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = asyncio.run(run_scan(Path(args.portals), args.limit, Path(args.output)))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
