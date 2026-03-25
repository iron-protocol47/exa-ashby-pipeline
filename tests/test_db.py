import json
import sqlite3

import pytest

from app.db.connection import connect, init_db
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
            ashby_job_id="job_a",
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
