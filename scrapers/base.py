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
    level: Optional[int] = None           # school-native: 200 (BYU) or 2100 (Utah)
    year_level: Optional[int] = None      # normalized standing: 1=fr..4=sr, 5+=grad
    description: str = ""
    college: str = ""
    department: str = ""
    career: str = ""           # e.g. Undergraduate / Graduate
    status: str = ""           # e.g. Active

    # Prerequisites. `prereq_tree` is the source of truth (see PrereqTree below);
    # the flat list and text are derived from it for display and graph queries.
    prereq_tree: Optional[dict] = None
    prerequisites: list[str] = field(default_factory=list)   # every code mentioned
    prerequisites_text: str = ""                             # e.g. "ACC 305 or ACC 310"

    # When the course is usually taught, as the catalog words it
    # (e.g. "Fall and Winter", "Winter Odd Years", "Contact Department").
    typically_offered: str = ""

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


def class_year_from_number(number: str) -> Optional[int]:
    """Normalize a course number to a class standing that means the same thing
    at every school: the leading digit. BYU 200 -> 2, Utah 2100 -> 2 (both
    sophomore); BYU 500 -> 5, Utah 6000 -> 6 (graduate)."""
    digits = ""
    for ch in str(number):
        if ch.isdigit():
            digits += ch
        else:
            break
    if not digits:
        return None
    return int(digits[0])


# --- Prerequisite trees -------------------------------------------------------
#
# Real prerequisites are logic, not lists: "ACC 305 or ACC 310", "(A and B) or C",
# "at least 2 of these 5". Every adapter converts its platform's format into this
# one neutral shape:
#
#   node := "ACC 200"                                   (a course code)
#         | {"op": "all",     "items": [node, ...]}     (every item required)
#         | {"op": "any",     "items": [node, ...]}     (one item is enough)
#         | {"op": "atleast", "n": 2, "items": [...]}   (n items required)


def make_node(op: str, items: list, n: Optional[int] = None):
    """Build a node, dropping empties and collapsing trivial nesting."""
    items = [i for i in items if i]
    if not items:
        return None
    if op in ("all", "any") and len(items) == 1:
        return items[0]
    node: dict[str, Any] = {"op": op, "items": items}
    if op == "atleast":
        node["n"] = n or 1
    return node


def tree_codes(node) -> list[str]:
    """Every course code mentioned in a tree (order kept, no duplicates)."""
    out: list[str] = []
    def walk(n):
        if isinstance(n, str):
            if n not in out:
                out.append(n)
        elif isinstance(n, dict):
            for i in n.get("items", []):
                walk(i)
    walk(node)
    return out


def tree_text(node, top: bool = True) -> str:
    """Readable form, e.g. 'ACC 200 and (ACC 305 or ACC 310)'."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    parts = [tree_text(i, top=False) for i in node["items"]]
    if node["op"] == "atleast":
        text = f"{node['n']} of: " + ", ".join(parts)
    else:
        text = f" {'and' if node['op'] == 'all' else 'or'} ".join(parts)
    return text if top else f"({text})"


def tree_satisfied(node, done: set[str]) -> bool:
    """Is this prerequisite tree satisfied by the set of completed codes?"""
    if node is None:
        return True
    if isinstance(node, str):
        return node in done
    results = [tree_satisfied(i, done) for i in node["items"]]
    if node["op"] == "all":
        return all(results)
    if node["op"] == "any":
        return any(results)
    return sum(results) >= node.get("n", 1)   # atleast


class CatalogAdapter:
    """Interface every platform adapter implements."""

    #: platform name, e.g. "coursedog"
    platform: str = "base"

    def fetch_courses(self, subject: Optional[str] = None) -> list[Course]:
        """Return normalized courses, optionally filtered to one subject code."""
        raise NotImplementedError
