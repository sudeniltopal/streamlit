"""Repository for Exam persistence."""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import List, Optional

from database.db import Database
from models.exam import Exam


def _parse_time(s: str):
    return datetime.strptime(s, "%H:%M").time()


class ExamRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def _row_to_model(self, row) -> Exam:
        return Exam(
            id=row["id"],
            course_code=row["course_code"],
            course_name=row["course_name"],
            department_type=row["department_type"],
            day=date.fromisoformat(row["day"]),
            start=_parse_time(row["start"]),
            end=_parse_time(row["end"]),
            required_invigilators=row["required_invigilators"],
            responsible_assistant_ids=json.loads(row["responsible_assistant_ids"]),
            only_responsible=bool(row["only_responsible"]),
            location=row["location"],
            notes=row["notes"],
        )

    def list_all(self) -> List[Exam]:
        return [self._row_to_model(r) for r in
                self.db.query("SELECT * FROM exams ORDER BY day, start")]

    def get(self, exam_id: int) -> Optional[Exam]:
        row = self.db.query_one("SELECT * FROM exams WHERE id = ?", (exam_id,))
        return self._row_to_model(row) if row else None

    def add(self, e: Exam) -> int:
        cur = self.db.execute(
            """INSERT INTO exams
               (course_code, course_name, department_type, day, start, end,
                required_invigilators, responsible_assistant_ids,
                only_responsible, location, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (e.course_code, e.course_name, e.department_type, e.day.isoformat(),
             e.start.strftime("%H:%M"), e.end.strftime("%H:%M"),
             e.required_invigilators,
             json.dumps(e.responsible_assistant_ids),
             int(e.only_responsible), e.location, e.notes),
        )
        return int(cur.lastrowid)

    def update(self, e: Exam) -> None:
        self.db.execute(
            """UPDATE exams SET
               course_code=?, course_name=?, department_type=?, day=?,
               start=?, end=?, required_invigilators=?,
               responsible_assistant_ids=?, only_responsible=?, location=?, notes=?
               WHERE id=?""",
            (e.course_code, e.course_name, e.department_type, e.day.isoformat(),
             e.start.strftime("%H:%M"), e.end.strftime("%H:%M"),
             e.required_invigilators, json.dumps(e.responsible_assistant_ids),
             int(e.only_responsible), e.location, e.notes, e.id),
        )

    def delete(self, exam_id: int) -> None:
        self.db.execute("DELETE FROM exams WHERE id = ?", (exam_id,))
