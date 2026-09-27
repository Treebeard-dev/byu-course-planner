"""Semesters, and whether a course is offered in one.

Catalogs describe schedules in loose English ("Fall and Winter", "Winter Odd
Years", "Contact Department"). `offered_in` turns that into three answers:

    True   the catalog says it's taught that term
    False  the catalog says it isn't (e.g. "Winter" only, and we're planning Fall)
    None   unknown ("Contact Department", blank) -> allowed, but flagged

Treating "unknown" as allowed-with-a-warning is a deliberate product choice:
about a third of BYU courses say "Contact Department", and blocking them would
quietly hide much of the catalog.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

SEASONS = ("fall", "winter", "spring", "summer")


@dataclass(frozen=True)
class Term:
    season: str          # e.g. "Winter"
    year: int            # e.g. 2027
    start_month: int     # month the term starts, for ordering and standing

    @property
    def label(self) -> str:
        return f"{self.season} {self.year}"

    @property
    def start(self) -> date:
        return date(self.year, self.start_month, 1)


def next_semesters(today: date, semesters: dict[str, int], n: int = 2) -> list[Term]:
    """The next `n` main semesters that start after `today`."""
    candidates = [
        Term(season, year, month)
        for year in range(today.year, today.year + 3)
        for season, month in semesters.items()
    ]
    upcoming = sorted((t for t in candidates if t.start > today), key=lambda t: t.start)
    return upcoming[:n]


def academic_year(d: date) -> int:
    """Academic years start in August: Sep 2026 and Jan 2027 are both 2026."""
    return d.year if d.month >= 8 else d.year - 1


def standing_for(year_in_school: int, term: Term, today: date) -> int:
    """Class standing during `term` (a sophomore today is a junior next Fall)."""
    return year_in_school + academic_year(term.start) - academic_year(today)


def offered_in(text: str, term: Term) -> Optional[bool]:
    """Is a course with this 'typically offered' text taught in `term`?"""
    t = (text or "").lower().strip()
    if not t:
        return None
    if "all semesters" in t or "all terms" in t or "every semester" in t:
        return True

    season = term.season.lower()
    mentioned = {s for s in SEASONS if s in t}
    clauses = [c.strip() for c in re.split(r"[;,.]| and ", t) if c.strip()]

    if season not in mentioned:
        if "contact department" in t or not mentioned:
            return None
        return False

    # Look at the clause(s) that name this season, for "odd/even years" or
    # "Contact Department" qualifiers ("Fall and Winter; Spring: Contact Department").
    own = [c for c in clauses if season in c]
    if any("contact department" in c for c in own):
        return None
    parity = None
    for c in own:
        if "odd year" in c:
            parity = "odd"
        elif "even year" in c:
            parity = "even"
    if parity is None and len(mentioned) == 1:
        parity = "odd" if "odd year" in t else "even" if "even year" in t else None
    if parity == "odd" and term.year % 2 == 0:
        return False
    if parity == "even" and term.year % 2 == 1:
        return False
    return True
