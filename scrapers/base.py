"""Shared shapes for all catalog adapters.

Every university's catalog runs on some vendor platform (Coursedog, Kuali,
CourseLeaf, ...). Each platform gets its own *adapter* that knows how to talk to
that platform, but they ALL return the same normalized `Course` shape defined
here. That is what lets the rest of the app treat every school the same way.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Any, Optional


@dataclass
class Course:
    """One course, normalized to a shape the whole app understands."""

    university: str            # school key, e.g. "byu"
    subject: str               # e.g. "ACC"
    number: str                # e.g. "200"
    code: str                  # e.g. "ACC 200"
    title: str                 # human title
    credits: Optional[float]   # credit hours (nominal value)
    credits_min: Optional[float] = None   # set when credits are variable
    credits_max: Optional[float] = None
    level: Optional[int] = None           # 100/200/300... derived from number
    description: str = ""
    college: str = ""
    department: str = ""
    career: str = ""           # e.g. Undergraduate / Graduate
    status: str = ""           # e.g. Active

    # Prerequisites, resolved to real course codes where possible.
    prerequisites: list[str] = field(default_factory=list)   # e.g. ["ACC 200"]
    prerequisites_text: str = ""                             # readable summary

    # Provenance / for scaling + freshness.
    source_id: str = ""        # the platform's internal id for this course
    fetched_at: str = ""       # ISO date the data was pulled
    catalog_year: str = ""     # catalog edition, when known

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def level_from_number(number: str) -> Optional[int]:
    """Turn a course number like '310R' into a level like 300."""
    digits = ""
    for ch in str(number):
        if ch.isdigit():
            digits += ch
        else:
            break
    if not digits:
        return None
    n = int(digits)
    return (n // 100) * 100


class CatalogAdapter:
    """Interface every platform adapter implements."""

    #: platform name, e.g. "coursedog"
    platform: str = "base"

    def fetch_courses(self, subject: Optional[str] = None) -> list[Course]:
        """Return normalized courses, optionally filtered to one subject code."""
        raise NotImplementedError
