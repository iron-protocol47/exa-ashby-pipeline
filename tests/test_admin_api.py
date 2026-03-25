from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


@pytest.fixture
def admin_client(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "adm.db"))
    monkeypatch.setenv("ADMIN_BASIC_USER", "admin")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "secret")
    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def test_admin_mappings_requires_config(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "noadmin.db"))
    monkeypatch.delenv("ADMIN_BASIC_USER", raising=False)
    monkeypatch.delenv("ADMIN_BASIC_PASSWORD", raising=False)
    get_settings.cache_clear()
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        r = c.get("/api/mappings")
    assert r.status_code == 503
    get_settings.cache_clear()


def test_admin_list_and_create(admin_client):
    r = admin_client.get("/api/mappings", auth=("admin", "secret"))
    assert r.status_code == 200
    assert r.json() == {"mappings": []}

    r2 = admin_client.post(
        "/api/mappings",
        auth=("admin", "secret"),
        json={
            "webset_id": "ws_x",
            "ashby_job_id": "job_y",
            "source_tag": "Tag",
            "active": True,
        },
    )
    assert r2.status_code == 200
    data = r2.json()
    assert data["websetId"] == "ws_x"
    assert data["ashbyJobId"] == "job_y"
    assert data["active"] is True

    r3 = admin_client.get("/api/mappings", auth=("admin", "secret"))
    assert len(r3.json()["mappings"]) == 1


def test_admin_rejects_bad_password(admin_client):
    r = admin_client.get("/api/mappings", auth=("admin", "wrong"))
    assert r.status_code == 401
