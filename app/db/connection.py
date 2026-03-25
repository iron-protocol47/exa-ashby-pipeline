from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from app.db import schema


def connect(path: Path) -> sqlite3.Connection:
    path = Path(path)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Path) -> None:
    """Create tables and record schema version."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(path)
    try:
        conn.executescript(schema.DDL)
        row = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (schema.SCHEMA_VERSION,),
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)",
                (schema.SCHEMA_VERSION,),
            )
            conn.commit()
        else:
            conn.commit()
    finally:
        conn.close()


@contextmanager
def connection_context(path: Path) -> Generator[sqlite3.Connection, None, None]:
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
