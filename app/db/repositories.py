from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.db.models import ActivityLogEntry, Mapping, PushedCandidate, mapping_from_row


def _norm_email(value: str | None) -> str | None:
    if value is None:
        return None
    s = value.strip().lower()
    return s if s else None


def _norm_url(value: str | None) -> str | None:
    if value is None:
        return None
    s = value.strip()
    return s if s else None


class MappingRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(
        self,
        *,
        webset_id: str,
        ashby_project_id: str,
        source_tag: str,
        active: bool = True,
        exa_webhook_id: str | None = None,
    ) -> int:
        cur = self._conn.execute(
            """
            INSERT INTO mappings (
              webset_id, ashby_project_id, source_tag, active, exa_webhook_id,
              updated_at
            ) VALUES (?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                webset_id.strip(),
                ashby_project_id.strip(),
                source_tag.strip(),
                1 if active else 0,
                exa_webhook_id,
            ),
        )
        return int(cur.lastrowid)

    def get_by_id(self, mapping_id: int) -> Mapping | None:
        row = self._conn.execute(
            "SELECT * FROM mappings WHERE id = ?", (mapping_id,)
        ).fetchone()
        return mapping_from_row(row) if row else None

    def get_by_webset_id(self, webset_id: str) -> Mapping | None:
        row = self._conn.execute(
            "SELECT * FROM mappings WHERE webset_id = ?", (webset_id.strip(),)
        ).fetchone()
        return mapping_from_row(row) if row else None

    def list_all(self) -> list[Mapping]:
        rows = self._conn.execute(
            "SELECT * FROM mappings ORDER BY created_at DESC"
        ).fetchall()
        return [mapping_from_row(r) for r in rows]

    def update(
        self,
        mapping_id: int,
        *,
        ashby_project_id: str | None = None,
        source_tag: str | None = None,
        active: bool | None = None,
        exa_webhook_id: str | None = None,
    ) -> None:
        fields: list[str] = []
        values: list[Any] = []
        if ashby_project_id is not None:
            fields.append("ashby_project_id = ?")
            values.append(ashby_project_id.strip())
        if source_tag is not None:
            fields.append("source_tag = ?")
            values.append(source_tag.strip())
        if active is not None:
            fields.append("active = ?")
            values.append(1 if active else 0)
        if exa_webhook_id is not None:
            fields.append("exa_webhook_id = ?")
            values.append(exa_webhook_id)
        if not fields:
            return
        fields.append("updated_at = datetime('now')")
        values.append(mapping_id)
        sql = f"UPDATE mappings SET {', '.join(fields)} WHERE id = ?"
        self._conn.execute(sql, values)

    def delete(self, mapping_id: int) -> None:
        self._conn.execute("DELETE FROM mappings WHERE id = ?", (mapping_id,))

    def record_push(self, mapping_id: int) -> None:
        self._conn.execute(
            """
            UPDATE mappings SET
              candidates_pushed_count = candidates_pushed_count + 1,
              last_sync_at = datetime('now'),
              updated_at = datetime('now')
            WHERE id = ?
            """,
            (mapping_id,),
        )


class PushedCandidateRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def insert(
        self,
        *,
        webset_id: str,
        exa_item_id: str | None,
        candidate_email: str | None,
        candidate_linkedin_url: str | None,
        ashby_candidate_id: str,
    ) -> int:
        email = _norm_email(candidate_email)
        li = _norm_url(candidate_linkedin_url)
        cur = self._conn.execute(
            """
            INSERT INTO pushed_candidates (
              webset_id, exa_item_id, candidate_email, candidate_linkedin_url,
              ashby_candidate_id
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                webset_id.strip(),
                exa_item_id.strip() if exa_item_id else None,
                email,
                li,
                ashby_candidate_id.strip(),
            ),
        )
        return int(cur.lastrowid)

    def row_to_model(self, row: sqlite3.Row) -> PushedCandidate:
        return PushedCandidate(
            id=row["id"],
            webset_id=row["webset_id"],
            exa_item_id=row["exa_item_id"],
            candidate_email=row["candidate_email"],
            candidate_linkedin_url=row["candidate_linkedin_url"],
            ashby_candidate_id=row["ashby_candidate_id"],
            pushed_at=row["pushed_at"],
        )

    def has_exa_item(self, webset_id: str, exa_item_id: str) -> bool:
        row = self._conn.execute(
            """
            SELECT 1 FROM pushed_candidates
            WHERE webset_id = ? AND exa_item_id = ?
            """,
            (webset_id.strip(), exa_item_id.strip()),
        ).fetchone()
        return row is not None

    def find_local_duplicate(
        self,
        webset_id: str,
        *,
        candidate_email: str | None,
        candidate_linkedin_url: str | None,
    ) -> bool:
        """True if this webset already pushed same email or LinkedIn URL locally."""
        wid = webset_id.strip()
        email = _norm_email(candidate_email)
        li = _norm_url(candidate_linkedin_url)
        if email:
            row = self._conn.execute(
                """
                SELECT 1 FROM pushed_candidates
                WHERE webset_id = ? AND candidate_email = ?
                """,
                (wid, email),
            ).fetchone()
            if row:
                return True
        if li:
            row = self._conn.execute(
                """
                SELECT 1 FROM pushed_candidates
                WHERE webset_id = ? AND candidate_linkedin_url = ?
                """,
                (wid, li),
            ).fetchone()
            if row:
                return True
        return False


class ActivityLogRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def append(
        self,
        event_type: str,
        *,
        webset_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> int:
        payload = details if details is not None else {}
        cur = self._conn.execute(
            """
            INSERT INTO activity_log (event_type, webset_id, details_json)
            VALUES (?, ?, ?)
            """,
            (
                event_type.strip(),
                webset_id.strip() if webset_id else None,
                json.dumps(payload, separators=(",", ":"), default=str),
            ),
        )
        return int(cur.lastrowid)

    def list_recent(self, *, limit: int = 200, offset: int = 0) -> list[ActivityLogEntry]:
        rows = self._conn.execute(
            """
            SELECT * FROM activity_log
            ORDER BY timestamp DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return [
            ActivityLogEntry(
                id=r["id"],
                timestamp=r["timestamp"],
                event_type=r["event_type"],
                webset_id=r["webset_id"],
                details_json=r["details_json"],
            )
            for r in rows
        ]
