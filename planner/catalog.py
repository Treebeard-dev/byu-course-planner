"""One university's courses and programs, loaded from the database.

A `Catalog` is always a single school: this is where the "one student, one
university" rule is enforced for everything downstream.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from scrapers.base import tree_codes
from universities import UNIVERSITIES

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "courses.db"

ALL_CONDITIONS = {"completedAllOf", "allOf"}
CHOOSE_CONDITIONS = {"completedAtLeastXOf", "completedAnyOf", "anyOf"}


@dataclass
class CourseInfo:
    code: str
    title: str
    credits: Optional[float]
    year_level: Optional[int]
    subject: str = ""
    college: str = ""
    offered: str = ""            # catalog wording, e.g. "Fall and Winter"
    tree: object = None          # prerequisite tree (see scrapers/base.py)
    description: str = ""
    variants: int = 1            # >1 for "topic" courses sharing one code


@dataclass
class RequirementGroup:
    name: str
    condition: str               # e.g. completedAllOf / completedAtLeastXOf
    courses: list[str]
    choose_n: Optional[int] = None

    @property
    def is_choose(self) -> bool:
        return self.condition in CHOOSE_CONDITIONS


@dataclass
class Program:
    name: str
    groups: list[RequirementGroup] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class Catalog:
    def __init__(self, university: str, courses: dict[str, CourseInfo],
                 programs: Optional[dict[str, Program]] = None):
        self.university = university
        self.courses = courses
        self.programs = programs or {}
        cfg = UNIVERSITIES.get(university, {})
        self.name = cfg.get("name", university)
        self.semesters: dict[str, int] = cfg.get("semesters", {"Spring": 1, "Fall": 8})
        self.full_time_credits: int = cfg.get("full_time_credits", 12)
        self.max_credits: int = cfg.get("max_credits", 18)
        self._unlocks: Optional[dict[str, set[str]]] = None

    def get(self, code: str) -> Optional[CourseInfo]:
        return self.courses.get(code)

    def program(self, name: str) -> Program:
        if name not in self.programs:
            known = ", ".join(sorted(self.programs)) or "(none loaded)"
            raise KeyError(f"No program '{name}' at {self.name}. Known: {known}")
        return self.programs[name]

    def unlocks(self, code: str) -> set[str]:
        """Courses that list `code` anywhere in their prerequisites."""
        if self._unlocks is None:
            rev: dict[str, set[str]] = {}
            for c in self.courses.values():
                for p in tree_codes(c.tree):
                    rev.setdefault(p, set()).add(c.code)
            self._unlocks = rev
        return self._unlocks.get(code, set())

    # -- loading ---------------------------------------------------------------
    @classmethod
    def from_db(cls, university: str, db_path: Path = DB_PATH) -> "Catalog":
        if not db_path.exists():
            raise FileNotFoundError(f"{db_path} not found - run build_db.py first.")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        courses: dict[str, CourseInfo] = {}
        for r in conn.execute(
            "SELECT * FROM courses WHERE university=? ORDER BY id", (university,)
        ):
            code = r["code"]
            if code in courses:              # another topic of the same code
                courses[code].variants += 1
                continue
            courses[code] = CourseInfo(
                code=code,
                title=r["title"] or "",
                credits=r["credits"],
                year_level=r["year_level"],
                subject=r["subject"] or "",
                college=r["college"] or "",
                offered=r["typically_offered"] or "",
                tree=json.loads(r["prereq_tree"]) if r["prereq_tree"] else None,
                description=r["description"] or "",
            )
        if not courses:
            raise KeyError(f"No courses loaded for '{university}'.")

        programs: dict[str, Program] = {}
        for p in conn.execute("SELECT id, name FROM programs WHERE university=?",
                              (university,)).fetchall():
            prog = Program(name=p["name"])
            groups: dict[tuple, RequirementGroup] = {}
            for row in conn.execute(
                "SELECT * FROM program_requirements WHERE program_id=? ORDER BY id",
                (p["id"],),
            ):
                if row["condition"] == "note":
                    prog.notes.append(row["notes"])
                    continue
                key = (row["requirement_group"], row["condition"])
                if key not in groups:
                    groups[key] = RequirementGroup(row["requirement_group"],
                                                   row["condition"], [], row["choose_n"])
                    prog.groups.append(groups[key])
                groups[key].courses.append(row["course_code"])
            programs[prog.name] = prog
        conn.close()
        return cls(university, courses, programs)
