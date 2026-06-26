"""End-to-end smoke test for the optimiser.

Seeds the demo data, runs the solver, prints the schedule + fairness report,
and asserts that every hard constraint is satisfied. Run from project root:

    python -m scripts.test_solver
"""
from __future__ import annotations

from database.db import Database
from optimization.solver import InvigilationSolver
from repositories.assistant_repo import AssistantRepository
from repositories.constraint_repo import ConstraintRepository
from repositories.exam_repo import ExamRepository
from scripts.seed_data import seed


def main() -> None:
    db = Database(":memory:")
    seed(db)

    assistants = AssistantRepository(db).list_all()
    exams = ExamRepository(db).list_all()
    constraints = ConstraintRepository(db).list_all()

    by_a = {a.id: a for a in assistants}
    by_e = {e.id: e for e in exams}

    result = InvigilationSolver(assistants, exams, constraints).solve()
    print(f"Status: {result.status.value}  ({result.solve_time_seconds}s)")

    if not result.feasible:
        print("INFEASIBLE. Diagnostics:")
        for d in result.diagnostics:
            print("  -", d)
        raise SystemExit(1)

    print("\nAssignments:")
    for eid, aids in sorted(result.assignments_by_exam().items()):
        e = by_e[eid]
        names = ", ".join(by_a[i].name for i in aids)
        print(f"  {e.course_code} {e.day} {e.start:%H:%M}-{e.end:%H:%M} "
              f"(need {e.required_invigilators}): {names}")

    print(f"\nDepartment average: {result.department_average}")
    print(f"Workload spread (max-min): {result.spread}")
    for s in sorted(result.workloads, key=lambda w: -w.total):
        sign = "+" if s.deviation >= 0 else ""
        print(f"  {s.assistant_name:12s} total={s.total} "
              f"(int={s.internal}, ext={s.external}, eve={s.evening}) "
              f"{sign}{s.deviation}")

    if result.warnings:
        print("\nWarnings:")
        for w in result.warnings:
            print("  *", w)

    # ---- assert hard constraints hold --------------------------------
    by_exam = result.assignments_by_exam()
    by_assistant = result.assignments_by_assistant()

    # Exact required count.
    for e in exams:
        assert len(by_exam.get(e.id, [])) == e.required_invigilators, \
            f"{e.course_code} wrong invigilator count"

    # Max workload.
    for a in assistants:
        used = len(by_assistant.get(a.id, []))
        assert a.current_count + used <= a.max_invigilations, \
            f"{a.name} exceeds max"

    # No time conflicts.
    for a in assistants:
        eids = by_assistant.get(a.id, [])
        for i in range(len(eids)):
            for j in range(i + 1, len(eids)):
                assert not by_e[eids[i]].overlaps(by_e[eids[j]]), \
                    f"{a.name} double-booked"

    # Availability respected.
    for a in assistants:
        for eid in by_assistant.get(a.id, []):
            e = by_e[eid]
            assert a.is_available_for(e.day, e.start, e.end), \
                f"{a.name} assigned while unavailable"

    # Forbidden pair (Kaya & Öztürk) never together.
    lee = next(a.id for a in assistants if a.name == "Mehmet Kaya")
    chen = next(a.id for a in assistants if a.name == "Can Öztürk")
    for eid, aids in by_exam.items():
        assert not (lee in aids and chen in aids), "forbidden pair co-assigned"

    print("\nAll hard-constraint assertions passed.")


if __name__ == "__main__":
    main()
