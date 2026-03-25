from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.config import get_settings
from app.slack.notify import send_slack_incoming


def test_send_slack_noop_without_url(monkeypatch):
    monkeypatch.delenv("SLACK_INCOMING_WEBHOOK_URL", raising=False)
    get_settings.cache_clear()
    settings = get_settings()
    # Should not raise
    send_slack_incoming(settings, "hello")


def test_send_slack_posts_when_url_set(monkeypatch):
    monkeypatch.setenv("SLACK_INCOMING_WEBHOOK_URL", "https://hooks.slack.com/services/test")
    get_settings.cache_clear()
    settings = get_settings()
    mock_post = MagicMock()
    monkeypatch.setattr("app.slack.notify.httpx.post", mock_post)
    send_slack_incoming(settings, "hello slack")
    mock_post.assert_called_once()
    call_kw = mock_post.call_args
    assert call_kw[0][0] == "https://hooks.slack.com/services/test"
    assert call_kw[1]["json"] == {"text": "hello slack"}
    get_settings.cache_clear()
