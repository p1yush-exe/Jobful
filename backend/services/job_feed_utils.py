from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


LINKEDIN_PATTERN = re.compile(r"linked\s*in|linkedin\.com", re.IGNORECASE)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_identity_part(value: Any) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class Job:
    source: str
    external_id: str
    title: str
    company: str
    location: str
    country: str
    description: str
    apply_url: str
    source_url: str
    publisher: str
    salary_min: float | None
    salary_max: float | None
    currency: str
    posted_at: str
    fetched_at: str
    raw_payload: dict[str, Any]
    ats_type: str | None = None
    ats_company_slug: str | None = None
    job_freshness_days: int | None = None

    @property
    def dedupe_key(self) -> tuple[str, str]:
        stable_id = self.external_id or self.apply_url or self.source_url or self.title
        identity = "|".join(
            [
                normalize_identity_part(stable_id),
                normalize_identity_part(self.country),
                normalize_identity_part(self.location),
            ]
        )
        return self.source, identity

    def mentions_linkedin(self) -> bool:
        fields = [
            self.apply_url,
            self.source_url,
            self.publisher,
            self.company,
            json.dumps(self.raw_payload, ensure_ascii=False),
        ]
        return any(LINKEDIN_PATTERN.search(value or "") for value in fields)


def dedupe_jobs(jobs: list[Job]) -> list[Job]:
    seen: set[tuple[str, str]] = set()
    unique_jobs: list[Job] = []
    for job in jobs:
        if job.dedupe_key in seen:
            continue
        seen.add(job.dedupe_key)
        unique_jobs.append(job)
    return unique_jobs


def write_json(jobs: list[Job], path: Path) -> None:
    rows = [asdict(job) for job in jobs]
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(jobs: list[Job], path: Path) -> None:
    fieldnames = [
        "source",
        "external_id",
        "title",
        "company",
        "location",
        "country",
        "publisher",
        "posted_at",
        "salary_min",
        "salary_max",
        "currency",
        "apply_url",
        "source_url",
        "description",
        "fetched_at",
        "ats_type",
        "ats_company_slug",
        "job_freshness_days",
    ]
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for job in jobs:
            row = asdict(job)
            row.pop("raw_payload", None)
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def write_text(jobs: list[Job], path: Path) -> None:
    lines: list[str] = []
    for index, job in enumerate(jobs, start=1):
        lines.extend(
            [
                f"{index}. {job.title}",
                f"Company: {job.company or 'Unknown'}",
                f"Location: {job.location or 'Unknown'}",
                f"Source: {job.source} / {job.publisher or 'Unknown'}",
                f"Posted: {job.posted_at or 'Unknown'}",
                f"Apply: {job.apply_url or job.source_url or 'No link'}",
                f"Description: {job.description[:500]}",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def export_jobs(jobs: list[Job], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_text(jobs, output_dir / "jobs.txt")
    write_csv(jobs, output_dir / "jobs.csv")
    write_json(jobs, output_dir / "jobs.json")
