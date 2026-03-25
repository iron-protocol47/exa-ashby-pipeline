from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.db.connection import connection_context
from app.exa.schemas import (
    item_id,
    item_person_candidate_fields,
    item_webset_id,
    parse_webhook_event,
)
from app.exa.signature import verify_webhook_signature
from app.sync.enriched_item import AshbySyncError, handle_enriched_item

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])

EVENT_ITEM_ENRICHED = "webset.item.enriched"


@router.post("/webhook")
async def exa_webhook(request: Request) -> Response:
    """
    Receives Exa `webset.item.enriched` (and other) webhooks.
    Verifies `Exa-Signature` using `EXA_WEBHOOK_SECRET` (see Exa docs).
    """
    settings = get_settings()
    body = await request.body()

    sig_header = request.headers.get("Exa-Signature") or request.headers.get(
        "exa-signature"
    )

    if settings.exa_skip_webhook_signature_verify:
        logger.warning("EXA_SKIP_WEBHOOK_SIGNATURE_VERIFY is on — not for production")
    else:
        if not settings.exa_webhook_secret:
            raise HTTPException(
                status_code=500,
                detail="EXA_WEBHOOK_SECRET is not configured",
            )
        if not verify_webhook_signature(
            body,
            sig_header,
            settings.exa_webhook_secret,
        ):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from e

    try:
        event = parse_webhook_event(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid webhook envelope") from e

    if event.type != EVENT_ITEM_ENRICHED:
        return Response(
            content=json.dumps({"ok": True, "ignored": True, "type": event.type}),
            media_type="application/json",
        )

    data = event.data
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Event data must be an object")

    ws_id = item_webset_id(data)
    exa_item = item_id(data)
    if not ws_id or not exa_item:
        raise HTTPException(
            status_code=400,
            detail="Missing websetId or item id on enriched item payload",
        )

    fields = item_person_candidate_fields(data)
    logger.info(
        "webset.item.enriched webset_id=%s item_id=%s name=%s",
        ws_id,
        exa_item,
        fields.get("name"),
    )

    def _run_sync() -> dict:
        with connection_context(settings.database_path) as conn:
            return handle_enriched_item(conn, settings, ws_id, exa_item, fields)

    try:
        payload_out = await run_in_threadpool(_run_sync)
    except AshbySyncError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return Response(
        content=json.dumps(payload_out),
        media_type="application/json",
    )
