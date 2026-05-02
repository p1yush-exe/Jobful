import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException, status

from db.executor import execute, fetch_all, fetch_one, fetch_one_commit
from db.query_loader import load_query


_FRESHNESS_TTL = timedelta(hours=1)
_FRESHNESS_TIMEOUT_SECONDS = 8
_FRESHNESS_MAX_PARALLEL = 6


_QUERIES_DIR = Path(__file__).resolve().parents[2] / "database" / "queries"

_VALID_STATUSES = {"interested", "applying", "applied", "response", "placed"}
_CLOSED_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"job (?:is )?no longer available",
        r"no longer accepting applications",
        r"applications (?:for this role )?(?:are )?closed",
        r"this position has been filled",
        r"position has been filled",
        r"job has expired",
        r"role is closed",
        r"vacancy closed",
        r"not accepting applications",
        r"posting has expired",
        r"this job is unavailable",
    ]
]


def list_user_applications(connection, user_id: str) -> list[dict[str, Any]]:
    rows = fetch_all(connection, load_query("applications", "get_user_applications.sql"), (user_id,))
    return [_serialize(r) for r in rows]


def get_applications_overview(connection, user_id: str) -> dict[str, Any]:
    refreshed_rows = _refresh_application_freshness(connection, user_id)
    items = [_serialize(row) for row in refreshed_rows]
    notifications = _build_notifications(items)
    return {
        "items": items,
        "notifications": notifications,
        "summary": {
            "total": len(items),
            "active": sum(1 for item in items if item.get("is_active", True)),
            "stale": len(notifications),
            "interested": sum(1 for item in items if item.get("status") == "interested"),
            "applying": sum(1 for item in items if item.get("status") == "applying"),
            "applied": sum(1 for item in items if item.get("status") in {"applied", "response", "placed"}),
        },
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    for key in ("applied_at", "updated_at", "posted_at", "last_checked_at", "stale_detected_at"):
        if key in out and out[key] is not None and not isinstance(out[key], str):
            out[key] = str(out[key])
    for key in ("application_id", "job_id", "user_id"):
        if key in out and out[key] is not None:
            out[key] = str(out[key])
    out["is_active"] = bool(out.get("is_active", True))
    return out


def track_job(connection, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Upsert job snapshot into `jobs`, then create/update application record."""
    source_name = payload.get("source", "jsearch")
    external_key = payload.get("external_id") or None

    # look up source_id
    source_row = fetch_one(connection, load_query("jobs", "get_source_id.sql"), (source_name,))
    source_id = str(source_row["source_id"]) if source_row else None

    # parse posted_at
    posted_at_raw = payload.get("posted_at") or ""
    try:
        posted_at = datetime.fromisoformat(posted_at_raw.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        posted_at = datetime.now(timezone.utc)

    # upsert job
    job_row = fetch_one(
        connection,
        load_query("jobs", "upsert_job.sql"),
        (
            source_id,
            payload.get("title", ""),
            payload.get("company", ""),
            payload.get("description", ""),
            payload.get("location") or None,
            payload.get("salary_range") or None,
            payload.get("apply_url") or payload.get("source_url") or None,
            payload.get("source_url") or payload.get("apply_url") or None,
            external_key,
            posted_at,
        ),
    )
    if not job_row:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to store job")
    job_id = str(job_row["job_id"])

    # create / update application
    init_status = payload.get("status", "interested")
    if init_status not in _VALID_STATUSES:
        init_status = "interested"

    app_row = fetch_one(
        connection,
        load_query("applications", "create_application.sql"),
        (user_id, job_id, init_status),
    )
    if not app_row:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create application")

    connection.commit()
    return {"application_id": str(app_row["application_id"]), "status": app_row["status"]}


def prepare_application_for_apply(connection, user_id: str, application_id: str) -> dict[str, Any]:
    row = fetch_one(
        connection,
        load_query("applications", "get_application_detail.sql"),
        (application_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found or not yours")

    serialized = _serialize(row)
    if not serialized.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This role is no longer accepting applications.")

    if serialized["status"] == "interested":
        update_application_status(connection, user_id, application_id, "applying")
        serialized["status"] = "applying"

    return {
        "application_id": application_id,
        "status": serialized["status"],
        "generation_status": "placeholder_pending",
        "apply_url": serialized.get("apply_url") or serialized.get("source_url"),
        "documents_to_generate": ["cv", "cover_letter"],
    }


def update_application_status(connection, user_id: str, application_id: str, new_status: str) -> dict[str, Any]:
    if new_status not in _VALID_STATUSES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid status: {new_status}")

    row = fetch_one(
        connection,
        load_query("applications", "update_application_status.sql"),
        (new_status, application_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found or not yours")

    connection.commit()
    return {"application_id": str(row["application_id"]), "status": row["status"]}


def remove_stale_interested_application(connection, user_id: str, application_id: str) -> dict[str, Any]:
    row = fetch_one(
        connection,
        load_query("applications", "get_application_detail.sql"),
        (application_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found or not yours")

    serialized = _serialize(row)
    if serialized.get("status") != "interested" or serialized.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only stale interested jobs can be removed right now.",
        )

    deleted = fetch_one_commit(
        connection,
        load_query("applications", "delete_application.sql"),
        (application_id, user_id),
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found or not yours")

    removed_job = fetch_one_commit(
        connection,
        load_query("jobs", "delete_orphan_job.sql"),
        (str(deleted["job_id"]),),
    )
    return {
        "application_id": application_id,
        "removed_job_id": str(removed_job["job_id"]) if removed_job else None,
    }


def get_application_summary_sql() -> str:
    return (_QUERIES_DIR / "get_application_summary.sql").read_text(encoding="utf-8")


def _is_freshness_cache_valid(row: dict[str, Any]) -> bool:
    last_checked = row.get("last_checked_at")
    if last_checked is None:
        return False
    if isinstance(last_checked, str):
        try:
            last_checked = datetime.fromisoformat(last_checked.replace("Z", "+00:00"))
        except ValueError:
            return False
    if last_checked.tzinfo is None:
        last_checked = last_checked.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - last_checked < _FRESHNESS_TTL


def _refresh_application_freshness(connection, user_id: str) -> list[dict[str, Any]]:
    rows = fetch_all(connection, load_query("applications", "get_user_applications.sql"), (user_id,))

    rows_to_check = [row for row in rows if not _is_freshness_cache_valid(row)]
    if not rows_to_check:
        return rows

    results: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
    with ThreadPoolExecutor(max_workers=_FRESHNESS_MAX_PARALLEL) as pool:
        futures = {pool.submit(_check_job_freshness, row): row for row in rows_to_check}
        for future, row in futures.items():
            try:
                results.append((row, future.result()))
            except Exception:
                results.append((row, None))

    changed = False
    for row, freshness in results:
        if freshness is None:
            continue
        changed = True
        execute(
            connection,
            load_query("jobs", "update_job_freshness.sql"),
            (
                freshness["is_active"],
                freshness["stale_reason"],
                freshness["is_active"],
                str(row["job_id"]),
            ),
        )

    if changed:
        connection.commit()
        return fetch_all(connection, load_query("applications", "get_user_applications.sql"), (user_id,))
    return rows


def _check_job_freshness(row: dict[str, Any]) -> dict[str, Any] | None:
    url = str(row.get("apply_url") or row.get("source_url") or "").strip()
    if not url:
        return None

    request = Request(
        url,
        headers={
            "User-Agent": "JobfulBot/1.0 (+job freshness check)",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urlopen(request, timeout=_FRESHNESS_TIMEOUT_SECONDS) as response:
            final_url = response.geturl() or url
            status_code = getattr(response, "status", None) or response.getcode()
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read(24576).decode(charset, errors="ignore")
    except HTTPError as exc:
        if exc.code in {404, 410, 451}:
            return {
                "is_active": False,
                "stale_reason": f"Listing returned HTTP {exc.code}.",
                "checked": True,
            }
        return None
    except URLError:
        return None
    except Exception:
        return None

    haystack = f"{final_url}\n{body}"
    if status_code in {404, 410, 451}:
        return {
            "is_active": False,
            "stale_reason": f"Listing returned HTTP {status_code}.",
            "checked": True,
        }
    for pattern in _CLOSED_PATTERNS:
        if pattern.search(haystack):
            return {
                "is_active": False,
                "stale_reason": "Listing appears closed or no longer accepting applications.",
                "checked": True,
            }
    return {"is_active": True, "stale_reason": None, "checked": True}


def _build_notifications(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    notifications: list[dict[str, Any]] = []
    for item in items:
        if item.get("is_active", True):
            continue
        status_text = str(item.get("status") or "")
        interested = status_text == "interested"
        notifications.append(
            {
                "application_id": item["application_id"],
                "job_id": item["job_id"],
                "status": status_text,
                "kind": "interested_stale" if interested else "applied_stale",
                "title": item.get("title") or "Unknown role",
                "company": item.get("company") or "Unknown company",
                "message": (
                    "This tracked role is no longer accepting applications. Remove it to keep your dashboard current."
                    if interested
                    else "A role in your application pipeline is now stale or closed. No action is wired yet."
                ),
                "stale_reason": item.get("stale_reason"),
                "stale_detected_at": item.get("stale_detected_at"),
                "can_remove": interested,
            }
        )
    notifications.sort(key=lambda notification: notification.get("stale_detected_at") or "", reverse=True)
    return notifications
