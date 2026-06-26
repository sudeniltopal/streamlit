"""Constraint handler registry.

Each administrator-defined :class:`Constraint` is translated into CP-SAT
constraints by a *handler* function registered against its
:class:`ConstraintType`. The solver simply loops over enabled constraints and
dispatches to the matching handler -- so supporting a new constraint type
means writing one function and decorating it with ``@register(...)``. The core
solver never changes.

Handlers receive a :class:`HandlerContext` exposing the model, the decision
variables, and lookup helpers, plus the specific ``Constraint`` instance.
Hard handlers add ``model.Add(...)`` constraints; soft handlers append
``(coefficient, expression)`` pairs to ``ctx.penalty_terms`` which the solver
folds into the objective.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional, Tuple

from ortools.sat.python import cp_model

from models.assistant import Assistant
from models.constraint import Constraint, ConstraintType
from models.exam import Exam


@dataclass
class HandlerContext:
    """Shared state passed to every constraint handler."""

    model: cp_model.CpModel
    assistants: List[Assistant]
    exams: List[Exam]
    # x[(assistant_id, exam_id)] -> BoolVar, only for *eligible* pairs.
    x: Dict[Tuple[int, int], cp_model.IntVar]
    # Soft-constraint penalty terms: (coefficient, linear_expr).
    penalty_terms: List[Tuple[int, object]] = field(default_factory=list)

    # ---- lookup helpers -------------------------------------------------
    def var(self, assistant_id: int, exam_id: int) -> Optional[cp_model.IntVar]:
        return self.x.get((assistant_id, exam_id))

    def exam(self, exam_id: int) -> Optional[Exam]:
        return next((e for e in self.exams if e.id == exam_id), None)

    def exams_on(self, day: date) -> List[Exam]:
        return [e for e in self.exams if e.day == day]


# Handler signature and registry -----------------------------------------
Handler = Callable[[HandlerContext, Constraint], None]
_REGISTRY: Dict[ConstraintType, Handler] = {}


def register(ctype: ConstraintType) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        _REGISTRY[ctype] = fn
        return fn
    return deco


def get_handler(ctype: ConstraintType) -> Optional[Handler]:
    return _REGISTRY.get(ctype)


# ====================================================================
# HARD constraint handlers
# ====================================================================
@register(ConstraintType.MUST_WORK_TOGETHER)
def _must_work_together(ctx: HandlerContext, c: Constraint) -> None:
    a, b = c.params["assistant_a"], c.params["assistant_b"]
    evening_only = bool(c.params.get("evening_only", False))
    scope = [e for e in ctx.exams if (e.is_evening if evening_only else True)]
    for e in scope:
        va, vb = ctx.var(a, e.id), ctx.var(b, e.id)
        if evening_only:
            # "If A assigned then B assigned" (one-directional implication).
            if va is None:
                continue
            if vb is None:
                ctx.model.Add(va == 0)   # partner unavailable -> A barred
            else:
                ctx.model.Add(vb >= va)
        else:
            # Symmetric: they are present together or not at all.
            if va is None and vb is None:
                continue
            if va is None:
                ctx.model.Add(vb == 0)
            elif vb is None:
                ctx.model.Add(va == 0)
            else:
                ctx.model.Add(va == vb)


@register(ConstraintType.CANNOT_WORK_TOGETHER)
def _cannot_work_together(ctx: HandlerContext, c: Constraint) -> None:
    a, b = c.params["assistant_a"], c.params["assistant_b"]
    for e in ctx.exams:
        va, vb = ctx.var(a, e.id), ctx.var(b, e.id)
        if va is not None and vb is not None:
            ctx.model.Add(va + vb <= 1)


@register(ConstraintType.ONLY_RESPONSIBLE)
def _only_responsible(ctx: HandlerContext, c: Constraint) -> None:
    e = ctx.exam(c.params["exam_id"])
    if e is None:
        return
    allowed = set(e.responsible_assistant_ids)
    for a in ctx.assistants:
        if a.id not in allowed:
            v = ctx.var(a.id, e.id)
            if v is not None:
                ctx.model.Add(v == 0)


@register(ConstraintType.FORBIDDEN_ASSISTANT)
def _forbidden_assistant(ctx: HandlerContext, c: Constraint) -> None:
    v = ctx.var(c.params["assistant_id"], c.params["exam_id"])
    if v is not None:
        ctx.model.Add(v == 0)


@register(ConstraintType.MAX_DAILY)
def _max_daily(ctx: HandlerContext, c: Constraint) -> None:
    limit = int(c.params["limit"])
    target = c.params.get("assistant_id")  # None -> applies to everyone
    targets = [a for a in ctx.assistants if target is None or a.id == target]
    days = sorted({e.day for e in ctx.exams})
    for a in targets:
        for d in days:
            day_vars = [ctx.var(a.id, e.id) for e in ctx.exams_on(d)]
            day_vars = [v for v in day_vars if v is not None]
            if day_vars:
                ctx.model.Add(sum(day_vars) <= limit)


@register(ConstraintType.MAX_WEEKLY)
def _max_weekly(ctx: HandlerContext, c: Constraint) -> None:
    limit = int(c.params["limit"])
    target = c.params.get("assistant_id")
    week_start = date.fromisoformat(c.params["week_start"])
    week_end = week_start + timedelta(days=7)
    week_exams = [e for e in ctx.exams if week_start <= e.day < week_end]
    targets = [a for a in ctx.assistants if target is None or a.id == target]
    for a in targets:
        wk_vars = [ctx.var(a.id, e.id) for e in week_exams]
        wk_vars = [v for v in wk_vars if v is not None]
        if wk_vars:
            ctx.model.Add(sum(wk_vars) <= limit)


# ====================================================================
# SOFT constraint handlers (contribute penalties to the objective)
# ====================================================================
@register(ConstraintType.PREFERRED_ASSISTANT)
def _preferred_assistant(ctx: HandlerContext, c: Constraint) -> None:
    weight = int(c.params.get("weight", 5))
    v = ctx.var(c.params["assistant_id"], c.params["exam_id"])
    if v is not None:
        # Penalise NOT assigning the preferred assistant: weight * (1 - v).
        ctx.penalty_terms.append((weight, 1 - v))


@register(ConstraintType.EVENING_RULE)
def _evening_rule(ctx: HandlerContext, c: Constraint) -> None:
    max_evening = int(c.params["max_evening"])
    weight = int(c.params.get("weight", 8))
    target = c.params.get("assistant_id")
    targets = [a for a in ctx.assistants if target is None or a.id == target]
    evening_exams = [e for e in ctx.exams if e.is_evening]
    for a in targets:
        ev_vars = [ctx.var(a.id, e.id) for e in evening_exams]
        ev_vars = [v for v in ev_vars if v is not None]
        if not ev_vars:
            continue
        excess = ctx.model.NewIntVar(0, len(ev_vars), f"eve_excess_{a.id}")
        ctx.model.Add(excess >= sum(ev_vars) - max_evening)
        ctx.penalty_terms.append((weight, excess))
