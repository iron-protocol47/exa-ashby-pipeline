from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.ashby.client import AshbyClient
from app.config import get_settings
from app.db.connection import connect, init_db
from app.db.repositories import MappingRepository

from tests.test_exa_webhook import _minimal_enriched_item


def _mock_ashby_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p.endswith("/candidate.create"):
            return httpx.Response(
                200,
                json={"results": {"candidate": {"id": "ashby-catch-1"}}},
            )
        if p.endswith("/candidate.addProject"):
            return httpx.Response(200, json={"success": True})
        return httpx.Response(404, text=f"unexpected {p}")

    return httpx.MockTransport(handler)


class _FakeExaClient:
    """Yields one webset item without calling Exa HTTP."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def __enter__(self) -> _FakeExaClient:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def close(self) -> None:
        pass

    def iter_items(self, webset_id: str):
        yield _minimal_enriched_item()


@pytest.fixture
def catch_up_client(monkeypatch, tmp_path):
    db = tmp_path / "catch.db"
    monkeypatch.setenv("DATABASE_PATH", str(db))
    monkeypatch.setenv("CATCH_UP_SECRET", "cron-secret-hex")
    monkeypatch.setenv("EXA_API_KEY", "exa-test-key")
    monkeypatch.setenv("ASHBY_API_KEY", "ashby-test-key")
    monkeypatch.setenv("DRY_RUN", "false")
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
    monkeypatch.setattr("app.routers.catch_up.ExaClient", _FakeExaClient)

    from app.main import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def test_catch_up_requires_secret_config(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "c.db"))
    monkeypatch.delenv("CATCH_UP_SECRET", raising=False)
    get_settings.cache_clear()
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        r = c.get("/catch-up", headers={"X-Cron-Secret": "x"})
    assert r.status_code == 503
    get_settings.cache_clear()


def test_catch_up_rejects_wrong_secret(catch_up_client):
    r = catch_up_client.get("/catch-up", headers={"X-Cron-Secret": "wrong"})
    assert r.status_code == 401


def test_catch_up_requires_exa_key(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "e.db"))
    monkeypatch.setenv("CATCH_UP_SECRET", "s")
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    get_settings.cache_clear()
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        r = c.get("/catch-up", headers={"X-Cron-Secret": "s"})
    assert r.status_code == 503
    assert "EXA_API_KEY" in r.json()["detail"]
    get_settings.cache_clear()


def test_catch_up_syncs_items(catch_up_client):
    r = catch_up_client.post(
        "/catch-up",
        headers={"X-Cron-Secret": "cron-secret-hex"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["mappingsProcessed"] == 1
    assert data["itemsExamined"] == 1
    assert data["synced"] == 1
    assert data["skipped"] == 0
    assert data["errors"] == []
