from __future__ import annotations

import logging
import sqlite3
from typing import Any

import httpx

from app.ashby.client import AshbyClient
from app.config import Settings
from app.db.repositories import (
    ActivityLogRepository,
    MappingRepository,
    PushedCandidateRepository,
)
from app.slack.notify import send_slack_incoming

logger = logging.getLogger(__name__)


class AshbySyncError(Exception):
    """Raised when Ashby API fails after logging; maps to HTTP 502 in the router."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


def _preview(fields: dict[str, str | None]) -> dict[str, str]:
    return {k: v for k, v in fields.items() if v}


def handle_enriched_item(
    conn: sqlite3.Connection,
    settings: Settings,
    webset_id: str,
    exa_item_id: str,
    fields: dict[str, str | None],
    *,
    ashby_client: AshbyClient | None = None,
) -> dict[str, Any]:
    """
    Resolve mapping, dedupe, optionally push to Ashby, record rows + activity_log.
    Caller owns the connection transaction (e.g. connection_context).
    """
    preview = _preview(fields)
    out: dict[str, Any] = {
        "ok": True,
        "websetId": webset_id,
        "itemId": exa_item_id,
        "preview": preview,
    }

    maps = MappingRepository(conn)
    log = ActivityLogRepository(conn)
    pc = PushedCandidateRepository(conn)

    mapping = maps.get_by_webset_id(webset_id)
    if mapping is None:
        log.append(
            "webhook.enriched.no_mapping",
            webset_id=webset_id,
            details={"itemId": exa_item_id},
        )
        out["synced"] = False
        out["skipReason"] = "no_mapping"
        return out

    if not mapping.active:
        log.append(
            "webhook.enriched.inactive_mapping",
            webset_id=webset_id,
            details={"mappingId": mapping.id, "itemId": exa_item_id},
        )
        out["synced"] = False
        out["skipReason"] = "inactive_mapping"
        return out

    if pc.has_exa_item(webset_id, exa_item_id):
        log.append(
            "webhook.enriched.duplicate_exa_item",
            webset_id=webset_id,
            details={"itemId": exa_item_id},
        )
        out["synced"] = False
        out["skipReason"] = "duplicate_exa_item"
        return out

    if pc.find_local_duplicate(
        webset_id,
        candidate_email=fields.get("email"),
        candidate_linkedin_url=fields.get("linkedin_url"),
    ):
        log.append(
            "webhook.enriched.duplicate_contact",
            webset_id=webset_id,
            details={"itemId": exa_item_id},
        )
        out["synced"] = False
        out["skipReason"] = "duplicate_contact"
        return out

    name = fields.get("name")
    email = fields.get("email")
    linkedin_url = fields.get("linkedin_url")
    if not name and not email and not linkedin_url:
        log.append(
            "webhook.enriched.insufficient_contact",
            webset_id=webset_id,
            details={"itemId": exa_item_id},
        )
        out["synced"] = False
        out["skipReason"] = "insufficient_contact"
        return out

    if settings.dry_run:
        log.append(
            "webhook.enriched.dry_run",
            webset_id=webset_id,
            details={"itemId": exa_item_id, "mappingId": mapping.id},
        )
        out["synced"] = False
        out["skipReason"] = "dry_run"
        return out

    api_key = (settings.ashby_api_key or "").strip()
    if not api_key:
        log.append(
            "webhook.enriched.no_ashby_key",
            webset_id=webset_id,
            details={"itemId": exa_item_id},
        )
        out["synced"] = False
        out["skipReason"] = "no_ashby_key"
        return out

    client = ashby_client
    if client is None:
        client = AshbyClient(api_key)

    try:
        ashby_cand_id = client.create_candidate_and_add_to_project(
            project_id=mapping.ashby_project_id,
            name=name,
            email=email,
            linkedin_url=linkedin_url,
        )
    except httpx.HTTPStatusError as e:
        log.append(
            "webhook.enriched.ashby_error",
            webset_id=webset_id,
            details={
                "itemId": exa_item_id,
                "status": e.response.status_code,
                "body": (e.response.text or "")[:2000],
            },
        )
        msg = f"Ashby API error: HTTP {e.response.status_code}"
        send_slack_incoming(
            settings,
            f"*Exa→Ashby* Ashby failure\nwebset `{webset_id}` item `{exa_item_id}`\n{msg}",
        )
        raise AshbySyncError(msg) from e
    except (ValueError, OSError) as e:
        log.append(
            "webhook.enriched.ashby_error",
            webset_id=webset_id,
            details={"itemId": exa_item_id, "error": str(e)},
        )
        msg = str(e)
        send_slack_incoming(
            settings,
            f"*Exa→Ashby* Ashby failure\nwebset `{webset_id}` item `{exa_item_id}`\n{msg}",
        )
        raise AshbySyncError(msg) from e

    pc.insert(
        webset_id=webset_id,
        exa_item_id=exa_item_id,
        candidate_email=email,
        candidate_linkedin_url=linkedin_url,
        ashby_candidate_id=ashby_cand_id,
    )
    maps.record_push(mapping.id)
    log.append(
        "webhook.enriched.synced",
        webset_id=webset_id,
        details={
            "itemId": exa_item_id,
            "ashbyCandidateId": ashby_cand_id,
            "mappingId": mapping.id,
        },
    )

    out["synced"] = True
    out["ashbyCandidateId"] = ashby_cand_id
    return out
