"""The optimisation engine (Google OR-Tools CP-SAT).

Responsibilities:
  * Build boolean decision variables x[a,e] only for *eligible* pairs.
  * Apply the structural hard constraints that are intrinsic to the problem
    (exact invigilator count, no time clashes, max workload, availability,
    responsible-only). These are always on.
  * Dispatch every enabled administrator-defined constraint to its handler.
  * Build a weighted fairness objective from the soft constraints.
  * Solve, then post-process into a rich :class:`SolveResult` including a
    fairness report and, on failure, human-readable infeasibility diagnostics.

The design goal from the spec -- "new constraints can be added without
rewriting the solver" -- is met by the handler registry: this file never
mentions a specific administrator constraint type by name.
"""
from __future__ import annotations

import statistics
from typing import Dict, List, Tuple

from ortools.sat.python import cp_model

from models.assignment import (Assignment, SolveResult, SolveStatus,
                               WorkloadStat)
from models.assistant import Assistant
from models.constraint import Constraint
from models.exam import Exam
from optimization.constraint_handlers import HandlerContext, get_handler

# Objective weights. Higher = the optimiser cares more. Fair-spread dominates,
# matching the spec's primary fairness goal (minimise max-min workload).
W_SPREAD = 100      # max load - min load (primary fairness)
W_DEVIATION = 12    # L1 distance of each load from the department target
W_IE_BALANCE = 6    # internal vs external balance
W_EVENING = 5       # even spread of evening duties
W_CONSECUTIVE = 4   # discourage piling exams onto one assistant in a day


class InvigilationSolver:
    """Encapsulates one optimisation run over a fixed dataset."""

    def __init__(self, assistants: List[Assistant], exams: List[Exam],
                 constraints: List[Constraint],
                 max_time_seconds: float = 20.0) -> None:
        self.assistants = assistants
        self.exams = exams
        self.constraints = [c for c in constraints if c.enabled]
        self.max_time_seconds = max_time_seconds

        self.model = cp_model.CpModel()
        self.x: Dict[Tuple[int, int], cp_model.IntVar] = {}
        self._by_assistant: Dict[int, Assistant] = {a.id: a for a in assistants}
        self._by_exam: Dict[int, Exam] = {e.id: e for e in exams}

    # ------------------------------------------------------------------
    # Model construction
    # ------------------------------------------------------------------
    def _eligible(self, a: Assistant, e: Exam) -> bool:
        """Pre-filter: can this assistant *possibly* take this exam?"""
        if not a.is_available_for(e.day, e.start, e.end):
            return False
        if e.only_responsible and a.id not in e.responsible_assistant_ids:
            return False
        return True

    def _build_variables(self) -> None:
        for a in self.assistants:
            for e in self.exams:
                if self._eligible(a, e):
                    self.x[(a.id, e.id)] = self.model.NewBoolVar(
                        f"x_a{a.id}_e{e.id}")

    def _vars_for_exam(self, e: Exam) -> List[cp_model.IntVar]:
        return [self.x[(a.id, e.id)] for a in self.assistants
                if (a.id, e.id) in self.x]

    def _vars_for_assistant(self, a: Assistant) -> List[cp_model.IntVar]:
        return [self.x[(a.id, e.id)] for e in self.exams
                if (a.id, e.id) in self.x]

    def _add_structural_constraints(self) -> None:
        # HARD 7: each exam gets exactly its required number of invigilators.
        for e in self.exams:
            self.model.Add(sum(self._vars_for_exam(e)) == e.required_invigilators)

        # HARD 6: nobody exceeds their max (net of pre-existing duties).
        for a in self.assistants:
            capacity = max(0, a.max_invigilations - a.current_count)
            av = self._vars_for_assistant(a)
            if av:
                self.model.Add(sum(av) <= capacity)

        # HARD 1: no assistant on two time-overlapping exams.
        for i in range(len(self.exams)):
            for j in range(i + 1, len(self.exams)):
                e1, e2 = self.exams[i], self.exams[j]
                if not e1.overlaps(e2):
                    continue
                for a in self.assistants:
                    v1 = self.x.get((a.id, e1.id))
                    v2 = self.x.get((a.id, e2.id))
                    if v1 is not None and v2 is not None:
                        self.model.Add(v1 + v2 <= 1)

        # HARD 2 (availability) and 3 (responsible-only) are enforced by the
        # eligibility pre-filter: ineligible pairs simply have no variable.

    def _apply_admin_constraints(self, ctx: HandlerContext) -> None:
        for c in self.constraints:
            handler = get_handler(c.type)
            if handler is not None:
                handler(ctx, c)

    # ------------------------------------------------------------------
    # Objective (soft constraints)
    # ------------------------------------------------------------------
    def _total_load_expr(self, a: Assistant):
        """current pre-existing duties + newly assigned ones."""
        av = self._vars_for_assistant(a)
        return a.current_count + (sum(av) if av else 0)

    def _build_objective(self, ctx: HandlerContext) -> None:
        objective_terms: List = []
        n = len(self.assistants)
        if n == 0:
            return

        loads = {a.id: self._total_load_expr(a) for a in self.assistants}
        upper = sum(e.required_invigilators for e in self.exams) + \
            max((a.current_count for a in self.assistants), default=0)

        # --- primary fairness: minimise (max load - min load) -------------
        max_load = self.model.NewIntVar(0, upper, "max_load")
        min_load = self.model.NewIntVar(0, upper, "min_load")
        for a in self.assistants:
            self.model.Add(max_load >= loads[a.id])
            self.model.Add(min_load <= loads[a.id])
        objective_terms.append(W_SPREAD * (max_load - min_load))

        # --- deviation from the department target (L1) --------------------
        total_slots = sum(e.required_invigilators for e in self.exams) + \
            sum(a.current_count for a in self.assistants)
        target = round(total_slots / n)
        for a in self.assistants:
            dev = self.model.NewIntVar(0, upper, f"dev_{a.id}")
            self.model.Add(dev >= loads[a.id] - target)
            self.model.Add(dev >= target - loads[a.id])
            objective_terms.append(W_DEVIATION * dev)

        # --- internal vs external balance (spread of internal duties) -----
        objective_terms += self._balance_spread(
            lambda e: e.department_type == "Internal", "int", W_IE_BALANCE)

        # --- evening fairness (spread of evening duties) ------------------
        objective_terms += self._balance_spread(
            lambda e: e.is_evening, "eve", W_EVENING)

        # --- discourage consecutive (multiple same-day) assignments -------
        days = sorted({e.day for e in self.exams})
        for a in self.assistants:
            for d in days:
                day_vars = [self.x[(a.id, e.id)] for e in self.exams
                            if e.day == d and (a.id, e.id) in self.x]
                if len(day_vars) > 1:
                    excess = self.model.NewIntVar(0, len(day_vars),
                                                  f"day_excess_a{a.id}_{d}")
                    self.model.Add(excess >= sum(day_vars) - 1)
                    objective_terms.append(W_CONSECUTIVE * excess)

        # --- soft constraints contributed by admin handlers --------------
        for coeff, expr in ctx.penalty_terms:
            objective_terms.append(coeff * expr)

        self.model.Minimize(sum(objective_terms))

    def _balance_spread(self, predicate, tag: str, weight: int) -> List:
        """Generic helper: minimise spread of a filtered duty count."""
        subset = [e for e in self.exams if predicate(e)]
        if not subset:
            return []
        upper = len(subset)
        counts = {}
        for a in self.assistants:
            vs = [self.x[(a.id, e.id)] for e in subset if (a.id, e.id) in self.x]
            counts[a.id] = sum(vs) if vs else 0
        hi = self.model.NewIntVar(0, upper, f"{tag}_hi")
        lo = self.model.NewIntVar(0, upper, f"{tag}_lo")
        for a in self.assistants:
            self.model.Add(hi >= counts[a.id])
            self.model.Add(lo <= counts[a.id])
        return [weight * (hi - lo)]

    # ------------------------------------------------------------------
    # Solve + post-process
    # ------------------------------------------------------------------
    def solve(self) -> SolveResult:
        self._build_variables()
        self._add_structural_constraints()
        ctx = HandlerContext(model=self.model, assistants=self.assistants,
                             exams=self.exams, x=self.x)
        self._apply_admin_constraints(ctx)
        self._build_objective(ctx)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.max_time_seconds
        solver.parameters.num_search_workers = 8
        status = solver.Solve(self.model)

        status_map = {
            cp_model.OPTIMAL: SolveStatus.OPTIMAL,
            cp_model.FEASIBLE: SolveStatus.FEASIBLE,
            cp_model.INFEASIBLE: SolveStatus.INFEASIBLE,
        }
        mapped = status_map.get(status, SolveStatus.UNKNOWN)
        result = SolveResult(status=mapped,
                             solve_time_seconds=round(solver.WallTime(), 3))

        if not result.feasible:
            result.diagnostics = self._diagnose_infeasibility()
            return result

        # Extract assignments.
        for (a_id, e_id), var in self.x.items():
            if solver.Value(var) == 1:
                result.assignments.append(Assignment(exam_id=e_id,
                                                      assistant_id=a_id))

        self._build_workload_report(result)
        return result

    def _build_workload_report(self, result: SolveResult) -> None:
        by_assistant = result.assignments_by_assistant()
        stats: List[WorkloadStat] = []
        for a in self.assistants:
            exam_ids = by_assistant.get(a.id, [])
            internal = sum(1 for eid in exam_ids
                           if self._by_exam[eid].department_type == "Internal")
            external = sum(1 for eid in exam_ids
                           if self._by_exam[eid].department_type == "External")
            evening = sum(1 for eid in exam_ids if self._by_exam[eid].is_evening)
            total = a.current_count + len(exam_ids)
            stats.append(WorkloadStat(
                assistant_id=a.id, assistant_name=a.name, total=total,
                internal=internal, external=external, evening=evening,
                deviation=0.0))

        totals = [s.total for s in stats]
        avg = round(statistics.fmean(totals), 2) if totals else 0.0
        for s in stats:
            s.deviation = round(s.total - avg, 2)

        result.workloads = stats
        result.department_average = avg
        result.spread = (max(totals) - min(totals)) if totals else 0
        result.warnings = self._build_fairness_warnings(stats, avg)

    def _build_fairness_warnings(self, stats: List[WorkloadStat],
                                 avg: float) -> List[str]:
        """Explain, in plain language, why over-loaded assistants are so."""
        warnings: List[str] = []
        for s in stats:
            if s.deviation < 1.5:           # only flag notable overloads
                continue
            a = self._by_assistant[s.assistant_id]
            reasons: List[str] = []

            # Reason: responsible for exclusive (responsible-only) courses.
            excl = [e.course_code for e in self.exams
                    if e.only_responsible and a.id in e.responsible_assistant_ids]
            if excl:
                reasons.append(
                    f"şu özel ders(ler)den sorumlu: {', '.join(excl)}")

            # Reason: bound by a 'must work together' pair.
            for c in self.constraints:
                if c.type.value == "must_work_together" and \
                        a.id in (c.params.get("assistant_a"),
                                 c.params.get("assistant_b")):
                    reasons.append("zorunlu eşleştirme kuralına tabi")
                    break

            # Reason: sole eligible assistant for some exam.
            forced = [e.course_code for e in self.exams
                      if len([1 for b in self.assistants
                              if self._eligible(b, e)]) <= e.required_invigilators
                      and self._eligible(a, e)]
            if forced:
                reasons.append(
                    f"şu sınav(lar) için tek uygun gözetmen: {', '.join(forced)}")

            detail = "; ".join(reasons) if reasons else \
                "diğer katı kısıtları dengelemek için gerekli"
            warnings.append(
                f"{a.name}, {s.total} görev üstleniyor "
                f"({avg} ortalamasına göre +{s.deviation}); sebep: {detail}.")
        return warnings

    def _diagnose_infeasibility(self) -> List[str]:
        """Heuristic explanation of why no feasible schedule exists."""
        reasons: List[str] = []

        # 1. Exams without enough eligible assistants.
        for e in self.exams:
            pool = [a for a in self.assistants if self._eligible(a, e)]
            if len(pool) < e.required_invigilators:
                why = []
                if e.only_responsible:
                    why.append("yalnızca sorumlu asistanlarla sınırlı")
                why.append("uygunluk kısıtları")
                reasons.append(
                    f"{e.day} tarihli {e.course_code} sınavı "
                    f"{e.required_invigilators} gözetmen gerektiriyor ancak "
                    f"yalnızca {len(pool)} uygun ({', '.join(why)}).")

        # 2. Aggregate capacity shortfall.
        demand = sum(e.required_invigilators for e in self.exams)
        capacity = sum(max(0, a.max_invigilations - a.current_count)
                       for a in self.assistants)
        if demand > capacity:
            reasons.append(
                f"Toplam ihtiyaç {demand} gözetmenlik iken toplam kalan "
                f"kapasite yalnızca {capacity}. Bazı üst limitleri artırın "
                f"veya asistan ekleyin.")

        if not reasons:
            reasons.append(
                "Eşleştirme / yasaklı çift / uygunluk kurallarının birleşimi "
                "tutarlı bir atamaya izin vermiyor. En kısıtlayıcı özel "
                "kuralları gevşetmeyi deneyin.")
        return reasons
