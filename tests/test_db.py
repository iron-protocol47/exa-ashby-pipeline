import json
import sqlite3

import pytest

from app.db.connection import _migrate_mappings_job_to_project, connect, init_db
from app.db.repositories import (
    ActivityLogRepository,
    MappingRepository,
    PushedCandidateRepository,
)


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "test.db"
    init_db(path)
    return path


def test_migrate_renames_ashby_job_column_to_project(tmp_path):
    """v1 DBs used ashby_job_id; migration renames to ashby_project_id."""
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE mappings (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          webset_id TEXT NOT NULL UNIQUE,
          ashby_job_id TEXT NOT NULL,
          source_tag TEXT NOT NULL,
          active INTEGER NOT NULL DEFAULT 1,
          exa_webhook_id TEXT,
          candidates_pushed_count INTEGER NOT NULL DEFAULT 0,
          last_sync_at TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO mappings (webset_id, ashby_job_id, source_tag)
        VALUES ('ws_legacy', 'job_old', 'tag');
        """
    )
    conn.commit()
    conn.close()

    conn = connect(path)
    try:
        _migrate_mappings_job_to_project(conn)
        conn.commit()
        row = conn.execute(
            "SELECT ashby_project_id FROM mappings WHERE webset_id = ?",
            ("ws_legacy",),
        ).fetchone()
        assert row is not None
        assert row[0] == "job_old"
    finally:
        conn.close()


def test_init_db_creates_tables(db_path):
    conn = connect(db_path)
    try:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        }
        assert "activity_log" in tables
        assert "mappings" in tables
        assert "pushed_candidates" in tables
        assert "schema_migrations" in tables
    finally:
        conn.close()


def test_mapping_crud_and_push_stats(db_path):
    conn = connect(db_path)
    try:
        maps = MappingRepository(conn)
        mid = maps.create(
            webset_id="ws_1",
            ashby_project_id="proj_a",
            source_tag="Tag",
            active=True,
        )
        assert mid == 1
        m = maps.get_by_webset_id("ws_1")
        assert m is not None
        assert m.candidates_pushed_count == 0
        assert m.last_sync_at is None

        maps.record_push(mid)
        conn.commit()
        m2 = maps.get_by_id(mid)
        assert m2 is not None
        assert m2.candidates_pushed_count == 1
        assert m2.last_sync_at is not None

        maps.update(mid, active=False)
        conn.commit()
        m3 = maps.get_by_id(mid)
        assert m3 is not None
        assert m3.active is False
    finally:
        conn.close()


def test_pushed_candidates_uniqueness_exa_item(db_path):
    conn = connect(db_path)
    try:
        pc = PushedCandidateRepository(conn)
        pc.insert(
            webset_id="ws_1",
            exa_item_id="item_1",
            candidate_email="a@b.com",
            candidate_linkedin_url=None,
            ashby_candidate_id="ash_1",
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            pc.insert(
                webset_id="ws_1",
                exa_item_id="item_1",
                candidate_email="other@b.com",
                candidate_linkedin_url=None,
                ashby_candidate_id="ash_2",
            )
    finally:
        conn.close()


def test_activity_log_json(db_path):
    conn = connect(db_path)
    try:
        log = ActivityLogRepository(conn)
        log.append("test.event", webset_id="ws_1", details={"x": 1})
        conn.commit()
        rows = log.list_recent(limit=5)
        assert len(rows) == 1
        assert rows[0].event_type == "test.event"
        assert json.loads(rows[0].details_json) == {"x": 1}
    finally:
        conn.close()
