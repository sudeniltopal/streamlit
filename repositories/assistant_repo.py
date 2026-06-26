"""Repository for Assistant persistence."""
from __future__ import annotations

import json
from datetime import date, datetime, time
from typing import List, Optional

from database.db import Database
from models.assistant import Assistant, UnavailabilitySlot


def _slot_to_dict(s: UnavailabilitySlot) -> dict:
    return {"day": s.day.isoformat(),
            "start": s.start.strftime("%H:%M"),
            "end": s.end.strftime("%H:%M")}


def _slot_from_dict(d: dict) -> UnavailabilitySlot:
    return UnavailabilitySlot(
        day=date.fromisoformat(d["day"]),
        start=datetime.strptime(d["start"], "%H:%M").time(),
        end=datetime.strptime(d["end"], "%H:%M").time(),
    )


class AssistantRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def _row_to_model(self, row) -> Assistant:
        return Assistant(
            id=row["id"],
            name=row["name"],
            academic_status=row["academic_status"],
            department=row["department"],
            email=row["email"],
            max_invigilations=row["max_invigilations"],
            min_invigilations=row["min_invigilations"],
            current_count=row["current_count"],
            responsible_courses=json.loads(row["responsible_courses"]),
            unavailability=[_slot_from_dict(d)
                            for d in json.loads(row["unavailability"])],
            personal_notes=row["personal_notes"],
        )

    def list_all(self) -> List[Assistant]:
        return [self._row_to_model(r)
                for r in self.db.query("SELECT * FROM assistants ORDER BY name")]

    def get(self, assistant_id: int) -> Optional[Assistant]:
        row = self.db.query_one("SELECT * FROM assistants WHERE id = ?",
                                (assistant_id,))
        return self._row_to_model(row) if row else None

    def add(self, a: Assistant) -> int:
        cur = self.db.execute(
            """INSERT INTO assistants
               (name, academic_status, department, email, max_invigilations,
                min_invigilations, current_count, responsible_courses,
                unavailability, personal_notes)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (a.name, a.academic_status, a.department, a.email,
             a.max_invigilations, a.min_invigilations, a.current_count,
             json.dumps(a.responsible_courses),
             json.dumps([_slot_to_dict(s) for s in a.unavailability]),
             a.personal_notes),
        )
        return int(cur.lastrowid)

    def update(self, a: Assistant) -> None:
        self.db.execute(
            """UPDATE assistants SET
               name=?, academic_status=?, department=?, email=?,
               max_invigilations=?, min_invigilations=?, current_count=?,
               responsible_courses=?, unavailability=?, personal_notes=?
               WHERE id=?""",
            (a.name, a.academic_status, a.department, a.email,
             a.max_invigilations, a.min_invigilations, a.current_count,
             json.dumps(a.responsible_courses),
             json.dumps([_slot_to_dict(s) for s in a.unavailability]),
             a.personal_notes, a.id),
        )

    def delete(self, assistant_id: int) -> None:
        self.db.execute("DELETE FROM assistants WHERE id = ?", (assistant_id,))
