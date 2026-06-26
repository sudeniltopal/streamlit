"""Domain model for an invigilation assistant (TA/RA).

Pure data container with type hints. Persistence is handled by the
repository layer, optimisation by the solver layer. Keeping the model
free of DB/solver logic is what lets each layer evolve independently.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from typing import List, Optional


@dataclass
class UnavailabilitySlot:
    """A single block of time during which the assistant cannot invigilate.

    We model *un*availability (rather than availability) because the common
    real-world input is "TA X is away on these dates", which is far sparser
    and easier for an administrator to enter than a full positive calendar.
    """

    day: date
    start: time
    end: time

    def covers(self, day: date, start: time, end: time) -> bool:
        """Return True if this slot overlaps the given exam window."""
        if day != self.day:
            return False
        # Two intervals overlap iff each starts before the other ends.
        return self.start < end and start < self.end


@dataclass
class Assistant:
    """A teaching/research assistant available for invigilation duty."""

    name: str
    academic_status: str = ""          # e.g. "PhD Student", "Research Assistant"
    department: str = ""
    email: str = ""
    max_invigilations: int = 6         # hard upper bound on workload
    min_invigilations: int = 0         # soft lower bound (desired floor)
    current_count: int = 0             # invigilations already assigned elsewhere
    responsible_courses: List[str] = field(default_factory=list)
    unavailability: List[UnavailabilitySlot] = field(default_factory=list)
    personal_notes: str = ""           # free-text personal constraints
    id: Optional[int] = None

    def is_available_for(self, day: date, start: time, end: time) -> bool:
        """True if no unavailability slot collides with the exam window."""
        return not any(slot.covers(day, start, end) for slot in self.unavailability)
