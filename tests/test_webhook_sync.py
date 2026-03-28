from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.ashby.client import AshbyClient
from app.config import get_settings
from app.db.connection import connect, init_db
from app.db.repositories import ActivityLogRepository, MappingRepository, PushedCandidateRepository

from tests.test_exa_webhook import _minimal_enriched_item


def _mock_ashby_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p.endswith("/candidate.create"):
            return httpx.Response(
                200,
                json={"results": {"candidate": {"id": "ashby-cand-99"}}},
            )
        if p.endswith("/candidate.addProject"):
            return httpx.Response(200, json={"success": True})
        return httpx.Response(404, text=f"unexpected {p}")

    return httpx.MockTransport(handler)


@pytest.fixture
def sync_client(monkeypatch, tmp_path):
    db = tmp_path / "sync.db"
    monkeypatch.setenv("DATABASE_PATH", str(db))
    monkeypatch.setenv("EXA_SKIP_WEBHOOK_SIGNATURE_VERIFY", "true")
    monkeypatch.setenv("ASHBY_API_KEY", "test-ashby-key")
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.setenv("BRANDON_ASHBY_USER_ID", "")
    get_settings.cache_clear()

    init_db(db)
    conn = connect(db)
    try:
        maps = MappingRepository(conn)
        maps.create(
            webset_id="ws_123",
            ashby_project_id="proj_ashby_1",
            source_tag="Exa",
            active=True,
        )
        conn.commit()
    finally:
        conn.close()

    def _ashby_factory(api_key: str) -> AshbyClient:
        return AshbyClient(api_key, transport=_mock_ashby_transport())

    monkeypatch.setattr("app.sync.enriched_item.AshbyClient", _ashby_factory)

    from app.main import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def test_webhook_syncs_when_mapping_and_ashby_ok(sync_client):
    body = {
        "id": "evt_s1",
        "type": "webset.item.enriched",
        "createdAt": "2026-01-01T00:00:00Z",
        "data": _minimal_enriched_item(),
    }
    raw = json.dumps(body)
    r = sync_client.post(
        "/webhook",
        content=raw,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 200
    out = r.json()
    assert out["ok"] is True
    assert out.get("synced") is True
    assert out.get("ashbyCandidateId") == "ashby-cand-99"

    settings = get_settings()
    conn = connect(settings.database_path)
    try:
        pc = PushedCandidateRepository(conn)
        assert pc.has_exa_item("ws_123", "item_abc")
        logs = ActivityLogRepository(conn).list_recent(limit=10)
        types = [x.event_type for x in logs]
        assert "webhook.enriched.synced" in types
    finally:
        conn.close()


def test_webhook_skips_duplicate_exa_item(sync_client):
    # First push
    body = {
        "id": "evt_s2",
        "type": "webset.item.enriched",
        "createdAt": "2026-01-01T00:00:00Z",
        "data": _minimal_enriched_item(),
    }
    raw = json.dumps(body)
    r1 = sync_client.post("/webhook", content=raw, headers={"Content-Type": "application/json"})
    assert r1.status_code == 200
    assert r1.json().get("synced") is True

    r2 = sync_client.post("/webhook", content=raw, headers={"Content-Type": "application/json"})
    assert r2.status_code == 200
    assert r2.json().get("synced") is False
    assert r2.json().get("skipReason") == "duplicate_exa_item"
