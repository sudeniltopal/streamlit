"""Domain model for a configurable constraint.

The whole point of this class is *data-driven* constraints: an administrator
defines a constraint by choosing a ``ConstraintType`` and filling a small
parameter dictionary. The solver's handler registry (see
``optimization/constraint_handlers.py``) translates each type into CP-SAT
constraints. Adding a new constraint type therefore means adding one enum
value and one handler function -- never touching the core solver loop.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class ConstraintType(str, Enum):
    """All administrator-definable constraint kinds.

    Each value's docstring lists the parameter keys its handler expects.
    'HARD' constraints are never violated; 'SOFT' ones contribute penalties
    to the objective.
    """

    # ----- HARD ------------------------------------------------------------
    MUST_WORK_TOGETHER = "must_work_together"
    # params: {"assistant_a": int, "assistant_b": int,
    #          "evening_only": bool (optional)}

    CANNOT_WORK_TOGETHER = "cannot_work_together"
    # params: {"assistant_a": int, "assistant_b": int}

    ONLY_RESPONSIBLE = "only_responsible"
    # params: {"exam_id": int}  -> only responsible assistants may invigilate

    FORBIDDEN_ASSISTANT = "forbidden_assistant"
    # params: {"exam_id": int, "assistant_id": int}

    MAX_DAILY = "max_daily"
    # params: {"assistant_id": int | None, "limit": int}

    MAX_WEEKLY = "max_weekly"
    # params: {"assistant_id": int | None, "limit": int, "week_start": "YYYY-MM-DD"}

    # ----- SOFT ------------------------------------------------------------
    PREFERRED_ASSISTANT = "preferred_assistant"
    # params: {"exam_id": int, "assistant_id": int, "weight": int (optional)}

    EVENING_RULE = "evening_rule"
    # params: {"assistant_id": int | None, "max_evening": int}


# Convenience set: which types are hard (used for UI grouping & validation).
HARD_TYPES = {
    ConstraintType.MUST_WORK_TOGETHER,
    ConstraintType.CANNOT_WORK_TOGETHER,
    ConstraintType.ONLY_RESPONSIBLE,
    ConstraintType.FORBIDDEN_ASSISTANT,
    ConstraintType.MAX_DAILY,
    ConstraintType.MAX_WEEKLY,
}


@dataclass
class Constraint:
    """A single configured constraint instance."""

    type: ConstraintType
    params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    description: str = ""
    id: Optional[int] = None

    @property
    def is_hard(self) -> bool:
        return self.type in HARD_TYPES
