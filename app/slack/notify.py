from __future__ import annotations

import logging

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


def send_slack_incoming(settings: Settings, text: str) -> None:
    """
    Post plain text to a Slack Incoming Webhook if SLACK_INCOMING_WEBHOOK_URL is set.
    Swallows errors so notification failures never break the pipeline.
    """
    url = (settings.slack_incoming_webhook_url or "").strip()
    if not url:
        return
    try:
        r = httpx.post(url, json={"text": text}, timeout=15.0)
        r.raise_for_status()
    except Exception as e:
        logger.warning("Slack incoming webhook failed: %s", e)
