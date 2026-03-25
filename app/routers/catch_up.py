from __future__ import annotations

import hmac
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.db.connection import connection_context
from app.db.repositories import MappingRepository
from app.exa.client import ExaClient
from app.exa.schemas import item_id, item_person_candidate_fields, item_webset_id
from app.slack.notify import send_slack_incoming
from app.sync.enriched_item import AshbySyncError, handle_enriched_item

logger = logging.getLogger(__name__)

router = APIRouter(tags=["cron"])


def _cron_secret_matches(provided: str, expected: str) -> bool:
    e = (expected or "").strip()
    g = (provided or "").strip()
    if not e:
        return False
    if len(g) != len(e):
        return False
    return hmac.compare_digest(g.encode("utf-8"), e.encode("utf-8"))


def _run_catch_up() -> dict[str, Any]:
    settings = get_settings()
    summary: dict[str, Any] = {
        "ok": True,
        "mappingsProcessed": 0,
        "itemsExamined": 0,
        "synced": 0,
        "skipped": 0,
        "errors": [],
    }

    with connection_context(settings.database_path) as conn:
        repo = MappingRepository(conn)
        active = [m for m in repo.list_all() if m.active]

    summary["mappingsProcessed"] = len(active)
    if not active:
        return summary

    api_key = (settings.exa_api_key or "").strip()
    if not api_key:
        raise RuntimeError("EXA_API_KEY is not configured")

    base = (settings.exa_base_url or "").strip() or "https://api.exa.ai/websets"

    with ExaClient(api_key, base_url=base) as exa:
        for m in active:
            for item in exa.iter_items(m.webset_id):
                summary["itemsExamined"] += 1
                if not isinstance(item, dict):
                    continue
                iid = item_id(item)
                if not iid:
                    continue
                wid = item_webset_id(item) or m.webset_id
                fields = item_person_candidate_fields(item)
                try:
                    with connection_context(settings.database_path) as conn:
                        out = handle_enriched_item(conn, settings, wid, iid, fields)
                    if out.get("synced"):
                        summary["synced"] += 1
                    else:
                        summary["skipped"] += 1
                except AshbySyncError as e:
                    err = {"websetId": wid, "itemId": iid, "detail": str(e)}
                    summary["errors"].append(err)
                    logger.warning("catch-up Ashby error %s", err)

    if summary["errors"]:
        lines = [
            f"• `{e['websetId']}` / `{e['itemId']}`: {e['detail']}"
            for e in summary["errors"][:15]
        ]
        more = len(summary["errors"]) - 15
        tail = f"\n… and {more} more" if more > 0 else ""
        send_slack_incoming(
            settings,
            f"*Exa→Ashby catch-up* {len(summary['errors'])} Ashby error(s)\n"
            + "\n".join(lines)
            + tail,
        )

    return summary


@router.api_route("/catch-up", methods=["GET", "POST"])
async def catch_up(request: Request) -> dict[str, Any]:
    """
    Poll Exa for items in each active mapping and push any not yet recorded.
    Secured with `X-Cron-Secret` matching `CATCH_UP_SECRET`.
    """
    settings = get_settings()
    expected = (settings.catch_up_secret or "").strip()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="CATCH_UP_SECRET is not configured",
        )

    got = request.headers.get("X-Cron-Secret") or ""
    if not _cron_secret_matches(got, expected):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing X-Cron-Secret header",
        )

    if not (settings.exa_api_key or "").strip():
        raise HTTPException(
            status_code=503,
            detail="EXA_API_KEY is not configured",
        )

    try:
        return await run_in_threadpool(_run_catch_up)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
