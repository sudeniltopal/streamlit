"""Domain model for an exam that requires invigilation."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from typing import List, Optional


@dataclass
class Exam:
    """A single exam session needing one or more invigilators."""

    course_code: str
    course_name: str = ""
    department_type: str = "Internal"   # "Internal" or "External"
    day: date = None                    # type: ignore[assignment]
    start: time = None                  # type: ignore[assignment]
    end: time = None                    # type: ignore[assignment]
    required_invigilators: int = 1
    responsible_assistant_ids: List[int] = field(default_factory=list)
    only_responsible: bool = False      # if True -> hard responsible restriction
    location: str = ""
    notes: str = ""
    id: Optional[int] = None

    # --- derived helpers used throughout the optimiser ------------------

    EVENING_THRESHOLD: time = time(17, 30)

    @property
    def is_evening(self) -> bool:
        """An exam counts as 'evening' if it starts at/after 17:30."""
        return self.start is not None and self.start >= self.EVENING_THRESHOLD

    def overlaps(self, other: "Exam") -> bool:
        """True if this exam's time window collides with another's."""
        if self.day != other.day:
            return False
        return self.start < other.end and other.start < self.end
