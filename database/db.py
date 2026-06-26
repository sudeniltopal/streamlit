"""SQLite persistence layer: connection management and schema bootstrap.

A single ``Database`` object owns the connection and exposes a thin cursor
helper. Repositories depend on this object, never on a global connection,
which keeps things testable (you can point a repository at an in-memory DB).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS assistants (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    academic_status     TEXT DEFAULT '',
    department          TEXT DEFAULT '',
    email               TEXT DEFAULT '',
    max_invigilations   INTEGER DEFAULT 6,
    min_invigilations   INTEGER DEFAULT 0,
    current_count       INTEGER DEFAULT 0,
    responsible_courses TEXT DEFAULT '[]',   -- JSON list of course codes
    unavailability      TEXT DEFAULT '[]',   -- JSON list of {day,start,end}
    personal_notes      TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS exams (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    course_code              TEXT NOT NULL,
    course_name              TEXT DEFAULT '',
    department_type          TEXT DEFAULT 'Internal',
    day                      TEXT NOT NULL,   -- ISO YYYY-MM-DD
    start                    TEXT NOT NULL,   -- HH:MM
    end                      TEXT NOT NULL,   -- HH:MM
    required_invigilators    INTEGER DEFAULT 1,
    responsible_assistant_ids TEXT DEFAULT '[]',  -- JSON list of assistant ids
    only_responsible         INTEGER DEFAULT 0,   -- 0/1 boolean
    location                 TEXT DEFAULT '',
    notes                    TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS constraints (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    type        TEXT NOT NULL,
    params      TEXT DEFAULT '{}',   -- JSON parameter object
    enabled     INTEGER DEFAULT 1,
    description TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS assignments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id      INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    assistant_id INTEGER NOT NULL REFERENCES assistants(id) ON DELETE CASCADE
);
"""


class Database:
    """Owns a single SQLite connection and the schema."""

    def __init__(self, path: str = "exam_system.db") -> None:
        self.path = path
        # check_same_thread=False so Streamlit's worker threads can share it.
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def execute(self, sql: str, params: Iterable = ()) -> sqlite3.Cursor:
        cur = self.conn.execute(sql, tuple(params))
        self.conn.commit()
        return cur

    def query(self, sql: str, params: Iterable = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, tuple(params)).fetchall()

    def query_one(self, sql: str, params: Iterable = ()) -> Optional[sqlite3.Row]:
        return self.conn.execute(sql, tuple(params)).fetchone()

    def reset(self) -> None:
        """Drop all rows (handy for re-seeding demo data)."""
        for table in ("assignments", "constraints", "exams", "assistants"):
            self.conn.execute(f"DELETE FROM {table};")
        self.conn.commit()


def default_db_path() -> str:
    """Place the DB next to the project root so runs are reproducible."""
    return str(Path(__file__).resolve().parent.parent / "exam_system.db")
