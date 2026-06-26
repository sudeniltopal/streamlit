"""Result objects produced by the optimiser."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List


class SolveStatus(str, Enum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    UNKNOWN = "UNKNOWN"


@dataclass
class Assignment:
    """One assistant assigned to one exam."""

    exam_id: int
    assistant_id: int


@dataclass
class WorkloadStat:
    """Per-assistant workload summary line for the fairness report."""

    assistant_id: int
    assistant_name: str
    total: int
    internal: int
    external: int
    evening: int
    deviation: float          # signed deviation from the department average


@dataclass
class SolveResult:
    """Everything the UI / exporters need after a solve attempt."""

    status: SolveStatus
    assignments: List[Assignment] = field(default_factory=list)
    workloads: List[WorkloadStat] = field(default_factory=list)
    department_average: float = 0.0
    spread: int = 0                      # max load - min load
    warnings: List[str] = field(default_factory=list)
    diagnostics: List[str] = field(default_factory=list)  # infeasibility reasons
    solve_time_seconds: float = 0.0

    @property
    def feasible(self) -> bool:
        return self.status in (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE)

    def assignments_by_exam(self) -> Dict[int, List[int]]:
        out: Dict[int, List[int]] = {}
        for a in self.assignments:
            out.setdefault(a.exam_id, []).append(a.assistant_id)
        return out

    def assignments_by_assistant(self) -> Dict[int, List[int]]:
        out: Dict[int, List[int]] = {}
        for a in self.assignments:
            out.setdefault(a.assistant_id, []).append(a.exam_id)
        return out
