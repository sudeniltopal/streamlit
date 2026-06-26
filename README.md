# University Exam Invigilation Assignment System

A single-administrator web app that automatically assigns invigilators
(teaching/research assistants) to exams, satisfying hard constraints and
optimising soft fairness goals with **Google OR-Tools (CP-SAT)**.

## Quick start

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then use the sidebar **Load demo data** button to populate a sample dataset, or
add your own assistants/exams/constraints. Click **Optimization → Generate
Schedule** to solve.

To try the engine without the UI:

```bash
python -m scripts.seed_data     # populate exam_system.db
python -m scripts.test_solver   # solve + assert all hard constraints hold
```

## Architecture

The codebase deliberately separates concerns so each layer can change
independently:

```
models/         Pure dataclasses (Assistant, Exam, Constraint, results)
database/       SQLite connection + schema
repositories/   CRUD + row⇄model serialisation (one per entity)
optimization/   CP-SAT solver + a registry of constraint handlers
reporting/      DataFrame builders + Excel/PDF exporters
ui/             Streamlit pages (dashboard, assistants, exams, constraints, optimization)
context.py      Wires the DB + repositories into one AppContext
app.py          Streamlit entry point
scripts/        Demo seeding + an end-to-end solver test
```

### How the optimiser is modelled

* **Decision variables:** one boolean `x[assistant, exam]` per *eligible* pair.
  Ineligible pairs (unavailable, or barred by a responsible-only exam) get no
  variable at all — that is how availability and responsible-only restrictions
  are enforced for free.
* **Structural hard constraints** (always on): exact required invigilator count,
  no time-overlap double-booking, and per-assistant maximum workload.
* **Administrator constraints** are *data-driven*: each is a `ConstraintType`
  plus a small params dict, stored in the DB. The solver loops over them and
  dispatches to a handler in `optimization/constraint_handlers.py`.
* **Soft objective** (weighted): minimise workload spread (max−min), L1
  deviation from the department average, internal/external imbalance, evening
  imbalance, same-day clustering, plus any soft-handler penalties.

### Adding a new constraint type (no solver changes)

1. Add a value to `ConstraintType` in `models/constraint.py`.
2. Write a handler in `optimization/constraint_handlers.py` and decorate it
   with `@register(ConstraintType.YOUR_TYPE)`.
3. Add its input widgets to `_param_form` in `ui/constraints_page.py`.

That's it — `optimization/solver.py` never needs editing.

## Hard vs soft constraints

| Hard (never violated)            | Soft (optimised, may yield)        |
|----------------------------------|------------------------------------|
| Time conflict                    | Fair workload (spread + deviation) |
| Availability                     | Internal vs external balance       |
| Responsible-only restriction     | Evening-exam balance               |
| Must / cannot work together      | Consecutive same-day clustering    |
| Forbidden assistant              | Preferred assistant                |
| Max workload (+ daily/weekly)    | Evening-rule soft caps             |
| Exact required invigilators      |                                    |

## Reports

* **Fairness report:** department average, signed per-assistant deviation, and
  plain-language warnings explaining *why* any assistant is over the average
  (exclusive courses, mandatory pairings, sole-available situations).
* **Constraint violation report:** when no feasible schedule exists, the solver
  returns actionable diagnostics (which exam lacks eligible invigilators,
  aggregate demand-vs-capacity shortfalls, etc.).

## Notes & assumptions

* Availability is entered as **un**availability blocks (sparser to type than a
  full positive calendar). An assistant is available unless a block overlaps the
  exam window.
* `current_count` is treated as pre-existing load and is included in fairness
  balancing and the max-workload limit.
* "Evening" = exam start at/after **17:30** (configurable in `models/exam.py`).
* SQLite is the default store; switch to PostgreSQL by replacing the connection
  in `database/db.py` (the repositories use standard SQL).
