"""Deterministic plan checks. No AI here: same plan in, same verdict out.

Errors make a plan invalid:
  - unknown course, already completed, or scheduled twice
  - prerequisites not completed in an EARLIER term (same-term doesn't count)
  - catalog says it isn't taught that term
  - semester over the credit limit

Warnings are things a student should know but that don't block the plan:
  - schedule unknown ("Contact Department")
  - course level above the student's standing, or graduate-level
  - semester under full-time
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from scrapers.base import tree_satisfied, tree_text
from .catalog import Catalog
from .models import Issue, Student
from .terms import Term, offered_in, standing_for


def validate_plan(catalog: Catalog, student: Student,
                  plan: list[tuple[Term, list[str]]],
                  today: Optional[date] = None) -> list[Issue]:
    today = today or date.today()
    max_credits = student.max_credits or catalog.max_credits
    done = set(student.completed)
    planned: set[str] = set()
    issues: list[Issue] = []

    for term, codes in plan:
        label = term.label
        standing = standing_for(student.year, term, today)
        credits = 0.0

        for code in codes:
            def add(sev: str, msg: str) -> None:
                issues.append(Issue(sev, label, code, msg))

            course = catalog.get(code)
            if course is None:
                add("error", f"Not a course at {catalog.name}.")
                continue
            if code in done and code not in planned:
                add("error", "Already completed.")
            elif code in planned and not code.endswith("R"):   # R = repeatable
                add("error", "Scheduled more than once.")

            if not tree_satisfied(course.tree, done):
                add("error", f"Prerequisites not met before {label}: "
                             f"needs {tree_text(course.tree)}.")

            when = offered_in(course.offered, term)
            if when is False:
                add("error", f"Not usually taught in {term.season} "
                             f"(catalog: '{course.offered}').")
            elif when is None:
                add("warning", f"Schedule not published (catalog: "
                               f"'{course.offered or 'blank'}') - confirm it runs in {label}.")

            lvl = course.year_level
            if lvl and lvl >= 5 and standing <= 4:
                add("warning", "Graduate-level course.")
            elif lvl and lvl > standing + 1:
                add("warning", f"Usually a year-{lvl} course; the student "
                               f"would be in year {standing}.")

            credits += course.credits or 0
            planned.add(code)

        if credits > max_credits:
            issues.append(Issue("error", label, "", f"{credits:g} credits is over the "
                                f"{max_credits}-credit limit."))
        elif credits < catalog.full_time_credits:
            issues.append(Issue("warning", label, "", f"{credits:g} credits is below "
                                f"full-time ({catalog.full_time_credits})."))

        done |= set(codes)   # available as prerequisites from the next term on

    return issues
