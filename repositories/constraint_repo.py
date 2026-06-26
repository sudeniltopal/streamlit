"""Repositories for Constraint and Assignment persistence."""
from __future__ import annotations

import json
from typing import List, Optional

from database.db import Database
from models.assignment import Assignment
from models.constraint import Constraint, ConstraintType


class ConstraintRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def _row_to_model(self, row) -> Constraint:
        return Constraint(
            id=row["id"],
            type=ConstraintType(row["type"]),
            params=json.loads(row["params"]),
            enabled=bool(row["enabled"]),
            description=row["description"],
        )

    def list_all(self, only_enabled: bool = False) -> List[Constraint]:
        sql = "SELECT * FROM constraints"
        if only_enabled:
            sql += " WHERE enabled = 1"
        sql += " ORDER BY id"
        return [self._row_to_model(r) for r in self.db.query(sql)]

    def get(self, cid: int) -> Optional[Constraint]:
        row = self.db.query_one("SELECT * FROM constraints WHERE id = ?", (cid,))
        return self._row_to_model(row) if row else None

    def add(self, c: Constraint) -> int:
        cur = self.db.execute(
            "INSERT INTO constraints (type, params, enabled, description) "
            "VALUES (?,?,?,?)",
            (c.type.value, json.dumps(c.params), int(c.enabled), c.description),
        )
        return int(cur.lastrowid)

    def update(self, c: Constraint) -> None:
        self.db.execute(
            "UPDATE constraints SET type=?, params=?, enabled=?, description=? "
            "WHERE id=?",
            (c.type.value, json.dumps(c.params), int(c.enabled),
             c.description, c.id),
        )

    def set_enabled(self, cid: int, enabled: bool) -> None:
        self.db.execute("UPDATE constraints SET enabled=? WHERE id=?",
                        (int(enabled), cid))

    def delete(self, cid: int) -> None:
        self.db.execute("DELETE FROM constraints WHERE id = ?", (cid,))


class AssignmentRepository:
    """Persists the latest generated schedule."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def replace_all(self, assignments: List[Assignment]) -> None:
        """Atomically swap in a freshly generated schedule."""
        self.db.execute("DELETE FROM assignments")
        for a in assignments:
            self.db.execute(
                "INSERT INTO assignments (exam_id, assistant_id) VALUES (?,?)",
                (a.exam_id, a.assistant_id),
            )

    def list_all(self) -> List[Assignment]:
        return [Assignment(exam_id=r["exam_id"], assistant_id=r["assistant_id"])
                for r in self.db.query("SELECT * FROM assignments")]

    def clear(self) -> None:
        self.db.execute("DELETE FROM assignments")
