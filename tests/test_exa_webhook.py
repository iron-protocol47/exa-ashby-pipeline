from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


def _sig(payload: str, secret: str) -> str:
    t = str(int(time.time()))
    sig = hmac.new(
        secret.encode("utf-8"),
        f"{t}.{payload}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return t, sig


@pytest.fixture
def client_webhook_skip_verify(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "wh.db"))
    monkeypatch.setenv("EXA_SKIP_WEBHOOK_SIGNATURE_VERIFY", "true")
    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


@pytest.fixture
def client_webhook_strict(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "wh2.db"))
    monkeypatch.setenv("EXA_WEBHOOK_SECRET", "whsec_strict")
    monkeypatch.setenv("EXA_SKIP_WEBHOOK_SIGNATURE_VERIFY", "false")
    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def _minimal_enriched_item() -> dict:
    return {
        "id": "item_abc",
        "object": "webset_item",
        "websetId": "ws_123",
        "source": "search",
        "sourceId": "src_1",
        "properties": {
            "type": "person",
            "url": "https://www.linkedin.com/in/someone",
            "description": "x",
            "person": {
                "name": "Jane Doe",
                "location": None,
                "position": None,
                "company": None,
                "pictureUrl": None,
            },
        },
        "evaluations": [],
        "enrichments": [
            {
                "object": "enrichment_result",
                "status": "completed",
                "format": "email",
                "result": ["jane@example.com"],
                "reasoning": None,
                "references": [],
                "enrichmentId": "enr_1",
            }
        ],
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }


def test_webhook_ignores_non_enriched_event(client_webhook_skip_verify):
    body = {
        "id": "evt_1",
        "type": "webset.created",
        "createdAt": "2026-01-01T00:00:00Z",
        "data": {"id": "ws_1"},
    }
    raw = json.dumps(body)
    r = client_webhook_skip_verify.post(
        "/webhook",
        content=raw,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data.get("ignored") is True


def test_webhook_enriched_parses_person_item(client_webhook_skip_verify):
    body = {
        "id": "evt_2",
        "type": "webset.item.enriched",
        "createdAt": "2026-01-01T00:00:00Z",
        "data": _minimal_enriched_item(),
    }
    raw = json.dumps(body)
    r = client_webhook_skip_verify.post(
        "/webhook",
        content=raw,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 200
    out = r.json()
    assert out["ok"] is True
    assert out["websetId"] == "ws_123"
    assert out["itemId"] == "item_abc"
    assert out["preview"]["name"] == "Jane Doe"
    assert out["preview"]["email"] == "jane@example.com"
    assert out.get("synced") is False
    assert out.get("skipReason") == "no_mapping"


def test_webhook_rejects_bad_signature(client_webhook_strict):
    body = {"id": "e", "type": "webset.created", "createdAt": "t", "data": {}}
    raw = json.dumps(body)
    r = client_webhook_strict.post(
        "/webhook",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "Exa-Signature": "t=1,v1=deadbeef",
        },
    )
    assert r.status_code == 401


def test_webhook_accepts_valid_signature(client_webhook_strict):
    body = {
        "id": "evt_3",
        "type": "webset.item.enriched",
        "createdAt": "2026-01-01T00:00:00Z",
        "data": _minimal_enriched_item(),
    }
    raw = json.dumps(body, separators=(",", ":"))
    t, sig = _sig(raw, "whsec_strict")
    r = client_webhook_strict.post(
        "/webhook",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "Exa-Signature": f"t={t},v1={sig}",
        },
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
