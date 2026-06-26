"""Populate the database with a small, realistic demo dataset.

Run with ``python -m scripts.seed_data`` from the project root. Useful both
for trying the app and as the fixture exercised by ``scripts.test_solver``.
"""
from __future__ import annotations

from datetime import date, time

from database.db import Database, default_db_path
from models.assistant import Assistant, UnavailabilitySlot
from models.constraint import Constraint, ConstraintType
from models.exam import Exam
from repositories.assistant_repo import AssistantRepository
from repositories.constraint_repo import ConstraintRepository
from repositories.exam_repo import ExamRepository


def seed(db: Database) -> None:
    db.reset()
    a_repo = AssistantRepository(db)
    e_repo = ExamRepository(db)
    c_repo = ConstraintRepository(db)

    # --- assistants ----------------------------------------------------
    ids = {}
    ids["smith"] = a_repo.add(Assistant(
        name="Ahmet Yılmaz", academic_status="Doktora Öğrencisi",
        department="EE", email="ahmet@uni.edu.tr",
        max_invigilations=8, min_invigilations=3,
        responsible_courses=["EE301"]))
    ids["jones"] = a_repo.add(Assistant(
        name="Ayşe Demir", academic_status="Araştırma Görevlisi",
        department="EE", email="ayse@uni.edu.tr",
        max_invigilations=8, min_invigilations=3))
    ids["lee"] = a_repo.add(Assistant(
        name="Mehmet Kaya", academic_status="Doktora Öğrencisi",
        department="EE", email="mehmet@uni.edu.tr",
        max_invigilations=8, min_invigilations=3,
        unavailability=[UnavailabilitySlot(date(2026, 5, 15),
                                           time(8, 0), time(23, 0))]))
    ids["garcia"] = a_repo.add(Assistant(
        name="Zeynep Şahin", academic_status="Araştırma Görevlisi",
        department="EE", email="zeynep@uni.edu.tr",
        max_invigilations=8, min_invigilations=3))
    ids["chen"] = a_repo.add(Assistant(
        name="Can Öztürk", academic_status="Doktora Öğrencisi",
        department="EE", email="can@uni.edu.tr",
        max_invigilations=8, min_invigilations=3))

    # --- exams ---------------------------------------------------------
    e_repo.add(Exam(course_code="EE301", course_name="Sinyaller", day=date(2026, 5, 14),
                    start=time(9, 0), end=time(11, 0), required_invigilators=2,
                    responsible_assistant_ids=[ids["smith"]], only_responsible=False,
                    location="A-101"))
    e_repo.add(Exam(course_code="EE205", course_name="Devreler", day=date(2026, 5, 14),
                    start=time(13, 0), end=time(15, 0), required_invigilators=2,
                    location="A-102"))
    e_repo.add(Exam(course_code="EE410", course_name="Kontrol Sistemleri", day=date(2026, 5, 14),
                    start=time(18, 0), end=time(20, 0), required_invigilators=2,
                    location="B-201"))   # evening exam (after 17:30)
    e_repo.add(Exam(course_code="EE150", course_name="EE'ye Giriş", day=date(2026, 5, 15),
                    start=time(9, 0), end=time(11, 0), required_invigilators=2,
                    department_type="External", location="C-301"))
    e_repo.add(Exam(course_code="EE320", course_name="Elektronik", day=date(2026, 5, 15),
                    start=time(13, 0), end=time(15, 0), required_invigilators=2,
                    location="A-101"))
    e_repo.add(Exam(course_code="EE499", course_name="Bitirme Projesi", day=date(2026, 5, 16),
                    start=time(10, 0), end=time(12, 0), required_invigilators=1,
                    location="A-105"))

    # --- constraints (data-driven) -------------------------------------
    # Must pair Yılmaz + Demir on evening exams.
    c_repo.add(Constraint(type=ConstraintType.MUST_WORK_TOGETHER,
                          params={"assistant_a": ids["smith"],
                                  "assistant_b": ids["jones"],
                                  "evening_only": True},
                          description="Yılmaz ve Demir akşam sınavlarında birlikte olmalı"))
    # Kaya and Öztürk must never supervise together.
    c_repo.add(Constraint(type=ConstraintType.CANNOT_WORK_TOGETHER,
                          params={"assistant_a": ids["lee"],
                                  "assistant_b": ids["chen"]},
                          description="Kaya ve Öztürk birlikte çalışamaz"))
    # Soft: cap evening duties at 1 each.
    c_repo.add(Constraint(type=ConstraintType.EVENING_RULE,
                          params={"assistant_id": None, "max_evening": 1},
                          description="Asistan başına 1'den fazla akşam görevini caydır"))


if __name__ == "__main__":
    database = Database(default_db_path())
    seed(database)
    print("Seeded demo data into", default_db_path())
