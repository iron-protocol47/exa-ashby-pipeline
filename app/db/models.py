from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Mapping:
    id: int
    webset_id: str
    ashby_job_id: str
    source_tag: str
    active: bool
    exa_webhook_id: str | None
    candidates_pushed_count: int
    last_sync_at: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class PushedCandidate:
    id: int
    webset_id: str
    exa_item_id: str | None
    candidate_email: str | None
    candidate_linkedin_url: str | None
    ashby_candidate_id: str
    pushed_at: str


@dataclass(frozen=True)
class ActivityLogEntry:
    id: int
    timestamp: str
    event_type: str
    webset_id: str | None
    details_json: str


def mapping_from_row(row: Any) -> Mapping:
    return Mapping(
        id=row["id"],
        webset_id=row["webset_id"],
        ashby_job_id=row["ashby_job_id"],
        source_tag=row["source_tag"],
        active=bool(row["active"]),
        exa_webhook_id=row["exa_webhook_id"],
        candidates_pushed_count=int(row["candidates_pushed_count"]),
        last_sync_at=row["last_sync_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
