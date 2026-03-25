"""SQLite persistence."""

from app.db.connection import connect, init_db

__all__ = ["connect", "init_db"]
