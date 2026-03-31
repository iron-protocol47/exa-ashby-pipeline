from __future__ import annotations

import httpx
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
            "ashby_project_id": "proj_y",
            "source_tag": "Tag",
            "active": True,
        },
    )
    assert r2.status_code == 200
    data = r2.json()
    assert data["websetId"] == "ws_x"
    assert data["ashbyProjectId"] == "proj_y"
    assert data["active"] is True

    r3 = admin_client.get("/api/mappings", auth=("admin", "secret"))
    assert len(r3.json()["mappings"]) == 1


def test_admin_rejects_bad_password(admin_client):
    r = admin_client.get("/api/mappings", auth=("admin", "wrong"))
    assert r.status_code == 401


def test_ashby_projects_requires_key(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "ap.db"))
    monkeypatch.setenv("ADMIN_BASIC_USER", "admin")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "secret")
    monkeypatch.delenv("ASHBY_API_KEY", raising=False)
    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as c:
        r = c.get("/api/ashby/projects", auth=("admin", "secret"))
    assert r.status_code == 503
    get_settings.cache_clear()


def test_ashby_projects_lists(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "ap2.db"))
    monkeypatch.setenv("ADMIN_BASIC_USER", "admin")
    monkeypatch.setenv("ADMIN_BASIC_PASSWORD", "secret")
    monkeypatch.setenv("ASHBY_API_KEY", "k")
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/project.list":
            return httpx.Response(
                200,
                json={
                    "results": {
                        "projects": [
                            {"id": "p1", "title": "Alpha"},
                            {"id": "p2", "title": "Beta"},
                        ]
                    }
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    from app.ashby.client import AshbyClient as RealAshbyClient
    from app.main import app
    from app.routers import admin_api

    monkeypatch.setattr(
        admin_api,
        "AshbyClient",
        lambda api_key, **kw: RealAshbyClient(api_key, transport=transport),
    )

    with TestClient(app) as c:
        r = c.get("/api/ashby/projects", auth=("admin", "secret"))
    assert r.status_code == 200
    data = r.json()
    assert data["projects"] == [
        {"id": "p1", "title": "Alpha"},
        {"id": "p2", "title": "Beta"},
    ]
    get_settings.cache_clear()


def test_patch_and_delete_mapping(admin_client):
    admin_client.post(
        "/api/mappings",
        auth=("admin", "secret"),
        json={
            "webset_id": "ws_a",
            "ashby_project_id": "proj_old",
            "source_tag": "t1",
            "active": True,
        },
    )
    r = admin_client.get("/api/mappings", auth=("admin", "secret"))
    mid = r.json()["mappings"][0]["id"]

    r2 = admin_client.patch(
        f"/api/mappings/{mid}",
        auth=("admin", "secret"),
        json={"ashby_project_id": "proj_new", "source_tag": "t2", "active": False},
    )
    assert r2.status_code == 200
    assert r2.json()["ashbyProjectId"] == "proj_new"
    assert r2.json()["sourceTag"] == "t2"
    assert r2.json()["active"] is False

    r3 = admin_client.delete(f"/api/mappings/{mid}", auth=("admin", "secret"))
    assert r3.status_code == 200
    assert admin_client.get("/api/mappings", auth=("admin", "secret")).json()["mappings"] == []


def test_admin_page_served():
    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as c:
        r = c.get("/admin")
    assert r.status_code == 200
    assert "Webset → Ashby project" in r.text
    get_settings.cache_clear()
