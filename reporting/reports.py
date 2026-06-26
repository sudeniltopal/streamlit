"""Turn a SolveResult + domain objects into pandas DataFrames.

Column headers are Turkish (used by on-screen tables, Excel and PDF alike);
the underlying field names stay English.
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from models.assignment import SolveResult
from models.assistant import Assistant
from models.exam import Exam

# Stored department type -> Turkish label.
DEPT_TYPE_TR = {"Internal": "Bölüm İçi", "External": "Bölüm Dışı"}


def assignments_dataframe(result: SolveResult, assistants: List[Assistant],
                          exams: List[Exam]) -> pd.DataFrame:
    by_a: Dict[int, Assistant] = {a.id: a for a in assistants}
    by_exam = result.assignments_by_exam()
    rows = []
    for e in exams:
        names = [by_a[i].name for i in by_exam.get(e.id, []) if i in by_a]
        rows.append({
            "Tarih": e.day.isoformat(),
            "Başlangıç": e.start.strftime("%H:%M"),
            "Bitiş": e.end.strftime("%H:%M"),
            "Ders": f"{e.course_code} — {e.course_name}".strip(" —"),
            "Tür": DEPT_TYPE_TR.get(e.department_type, e.department_type),
            "Yer": e.location,
            "Gerekli": e.required_invigilators,
            "Atanan": ", ".join(names) if names else "—",
        })
    return pd.DataFrame(rows)


def workload_dataframe(result: SolveResult) -> pd.DataFrame:
    rows = []
    for s in sorted(result.workloads, key=lambda w: -w.total):
        rows.append({
            "Asistan": s.assistant_name,
            "Toplam": s.total,
            "Bölüm İçi": s.internal,
            "Bölüm Dışı": s.external,
            "Akşam": s.evening,
            "Sapma": f"{'+' if s.deviation >= 0 else ''}{s.deviation}",
        })
    return pd.DataFrame(rows)
