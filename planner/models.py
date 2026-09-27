"""The shapes passed between the validator, recommender, and (later) the web app."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .terms import Term


@dataclass
class Student:
    university: str
    program: str                      # e.g. "Accounting BS"
    year: int                         # 1 = freshman ... 4 = senior
    completed: set[str] = field(default_factory=set)
    target_credits: int = 15          # what we aim for per semester
    max_credits: Optional[int] = None   # defaults to the school's limit


@dataclass
class Issue:
    severity: str                     # "error" (plan is invalid) | "warning"
    term: str
    code: str
    message: str


@dataclass
class Pick:
    code: str
    title: str
    credits: float
    kind: str                         # "required" | "elective" | "breadth"
    reason: str


@dataclass
class TermPlan:
    term: Term
    standing: int
    picks: list[Pick] = field(default_factory=list)
    alternates: list[Pick] = field(default_factory=list)

    @property
    def credits(self) -> float:
        return sum(p.credits for p in self.picks)


@dataclass
class PlanResult:
    student: Student
    terms: list[TermPlan]
    issues: list[Issue]
    program_notes: list[str]
    still_required: list[str]         # required courses left after this plan
