import pytest


@pytest.fixture
def client(monkeypatch, tmp_path):
    """App TestClient with isolated SQLite path and fresh settings cache."""
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))

    from app.config import get_settings

    get_settings.cache_clear()

    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()
