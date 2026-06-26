"""A small service container so UI pages get one object, not five repos.

Streamlit re-runs the script top to bottom on every interaction, so we cache a
single ``AppContext`` in ``st.session_state`` (see ``app.py``). The context owns
the database connection and exposes ready-made repositories.
"""
from __future__ import annotations

from database.db import Database, default_db_path
from repositories.assistant_repo import AssistantRepository
from repositories.constraint_repo import AssignmentRepository, ConstraintRepository
from repositories.exam_repo import ExamRepository


class AppContext:
    def __init__(self, db_path: str | None = None) -> None:
        self.db = Database(db_path or default_db_path())
        self.assistants = AssistantRepository(self.db)
        self.exams = ExamRepository(self.db)
        self.constraints = ConstraintRepository(self.db)
        self.assignments = AssignmentRepository(self.db)
