"""Coursedog catalog adapter (BYU, University of Utah, Utah State, and many more).

Coursedog-powered catalogs are backed by a public JSON API. There is no login,
but the API only answers when the request carries the school's catalog site in
its Origin/Referer headers. We:

  1. page through the FULL catalog once (needed to resolve prerequisites),
  2. build a lookup from each course's internal `courseGroupId` to its code,
  3. normalize every course and translate prerequisite ids into real codes.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Any, Optional

import requests

from .base import Course, CatalogAdapter, level_from_number, class_year_from_number

API_ROOT = "https://app.coursedog.com/api/v1/cm"

# The columns we ask the API to return for each course.
COLUMNS = ",".join([
    "name", "longName", "subjectCode", "courseNumber", "code",
    "credits.creditHours", "description", "college", "departments",
    "career", "status", "requisites", "courseGroupId",
])


class CoursedogAdapter(CatalogAdapter):
    platform = "coursedog"

    def __init__(
        self,
        university: str,
        school_id: str,
        catalog_id: str,
        catalog_host: str,
        page_size: int = 500,
        delay_seconds: float = 0.3,
    ):
        self.university = university
        self.school_id = school_id
        self.catalog_id = catalog_id
        self.catalog_host = catalog_host.rstrip("/")
        self.page_size = page_size
        self.delay_seconds = delay_seconds

        self.session = requests.Session()
        self.session.headers.update({
            "Origin": self.catalog_host,
            "Referer": self.catalog_host + "/",
            "Accept": "application/json",
            "User-Agent": "byu-course-planner/0.1 (student project; contact via GitHub Treebeard-dev)",
        })

    # -- low-level: pull every raw course record from the API -----------------
    def _fetch_raw(self) -> list[dict[str, Any]]:
        url = f"{API_ROOT}/{self.school_id}/courses/search/$filters"
        params = {
            "catalogId": self.catalog_id,
            "skip": 0,
            "limit": self.page_size,
            "orderBy": "code",
            "columns": COLUMNS,
        }
        out: list[dict[str, Any]] = []
        total = None
        while True:
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            payload = resp.json()
            if total is None:
                total = payload.get("listLength", 0)
            batch = payload.get("data", [])
            out.extend(batch)
            if not batch or len(out) >= total:
                break
            params["skip"] += self.page_size
            time.sleep(self.delay_seconds)
        return out

    # -- helpers --------------------------------------------------------------
    @staticmethod
    def _code_for(raw: dict[str, Any]) -> str:
        subj = (raw.get("subjectCode") or "").strip()
        num = str(raw.get("courseNumber") or "").strip()
        if subj and num:
            return f"{subj} {num}"
        return (raw.get("code") or "").strip()

    @staticmethod
    def _credits(raw: dict[str, Any]) -> tuple[Optional[float], Optional[float], Optional[float]]:
        ch = ((raw.get("credits") or {}).get("creditHours") or {})
        val = ch.get("value")
        cmin = ch.get("min")
        cmax = ch.get("max")
        def num(x):
            try:
                return float(x)
            except (TypeError, ValueError):
                return None
        val, cmin, cmax = num(val), num(cmin), num(cmax)
        if val is None:
            val = cmin
        variable = (cmin is not None and cmax is not None and cmin != cmax)
        return val, (cmin if variable else None), (cmax if variable else None)

    @staticmethod
    def _collect_ids(node: Any) -> list[str]:
        """Recursively pull course-group ids out of a Coursedog rule value.

        Coursedog nests these differently from school to school (sometimes a
        list of objects, sometimes plain strings), so we walk the structure and
        collect anything that looks like a course id (contains a digit), ignoring
        logic keywords like "and"/"or". De-duplicated, order preserved.
        """
        ids: list[str] = []

        def walk(n: Any) -> None:
            if isinstance(n, str):
                if n not in ("and", "or") and any(ch.isdigit() for ch in n):
                    ids.append(n)
            elif isinstance(n, list):
                for item in n:
                    walk(item)
            elif isinstance(n, dict):
                for key in ("values", "value", "subSelections"):
                    if key in n:
                        walk(n[key])

        walk(node)
        seen: set[str] = set()
        unique: list[str] = []
        for gid in ids:
            if gid not in seen:
                seen.add(gid)
                unique.append(gid)
        return unique

    def _prereq_group_ids(self, raw: dict[str, Any]) -> list[str]:
        """The courseGroupIds a course lists as prerequisites."""
        ids: list[str] = []
        req = raw.get("requisites") or {}
        for block in (req.get("requisitesSimple") or []):
            if block.get("type") != "Prerequisite":
                continue
            for rule in block.get("rules", []):
                ids.extend(self._collect_ids(rule.get("value")))
        seen: set[str] = set()
        return [g for g in ids if not (g in seen or seen.add(g))]

    # -- public: normalized courses ------------------------------------------
    def fetch_courses(self, subject: Optional[str] = None) -> list[Course]:
        raw_courses = self._fetch_raw()
        today = date.today().isoformat()

        # lookup: internal courseGroupId -> readable code, for prereq resolution
        gid_to_code = {
            r.get("courseGroupId"): self._code_for(r)
            for r in raw_courses
            if r.get("courseGroupId")
        }

        courses: list[Course] = []
        for r in raw_courses:
            if (r.get("status") or "") != "Active":
                continue
            subj = (r.get("subjectCode") or "").strip()
            if not subj:
                continue
            name = (r.get("name") or "").strip()
            if "test" in name.lower():   # drop obvious test rows
                continue
            if subject and subj.upper() != subject.upper():
                continue

            val, cmin, cmax = self._credits(r)
            prereq_codes = [
                gid_to_code[g] for g in self._prereq_group_ids(r)
                if g in gid_to_code
            ]
            number = str(r.get("courseNumber") or "").strip()

            courses.append(Course(
                university=self.university,
                subject=subj,
                number=number,
                code=self._code_for(r),
                title=(r.get("longName") or name).strip(),
                credits=val,
                credits_min=cmin,
                credits_max=cmax,
                level=level_from_number(number),
                year_level=class_year_from_number(number),
                description=(r.get("description") or "").strip(),
                college=(r.get("college") or "").strip(),
                department=", ".join(
                    d.get("name", "") for d in (r.get("departments") or [])
                    if isinstance(d, dict)
                ),
                career=(r.get("career") or "").strip(),
                status=(r.get("status") or "").strip(),
                prerequisites=prereq_codes,
                prerequisites_text=(
                    ", ".join(prereq_codes) if prereq_codes else ""
                ),
                source_id=r.get("courseGroupId") or "",
                fetched_at=today,
                catalog_year=self.catalog_id,
            ))
        return courses

    # -- program requirements -------------------------------------------------
    def _course_lookup(self) -> dict[str, str]:
        """courseGroupId -> code, cached so we only pull the catalog once."""
        if not hasattr(self, "_gid_cache"):
            self._gid_cache = {
                r.get("courseGroupId"): self._code_for(r)
                for r in self._fetch_raw()
                if r.get("courseGroupId")
            }
        return self._gid_cache

    def fetch_program(self, program_id: str) -> dict[str, Any]:
        """Fetch one program's requirements, resolved to real course codes.

        Returns a normalized dict. Course-list rules become resolved code lists;
        freeform/grade/timing rules are kept as human-readable notes rather than
        parsed (see CLAUDE.md: we plan, we do not run a full degree audit).
        """
        url = f"{API_ROOT}/{self.school_id}/programs/{program_id}"
        resp = self.session.get(url, params={"catalogId": self.catalog_id}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and isinstance(data.get("data"), dict):
            data = data["data"]

        lookup = self._course_lookup()
        requirements: list[dict[str, Any]] = []

        req = data.get("requisites") or {}
        for block in (req.get("requisitesSimple") or []):
            group = block.get("name") or "Requirement"
            for rule in block.get("rules", []):
                cond = rule.get("condition")
                if cond == "freeformText":
                    requirements.append({
                        "group": group,
                        "condition": "note",
                        "courses": [],
                        "choose_n": None,
                        "note": (rule.get("value") or "").strip(),
                    })
                    continue
                value = rule.get("value") or {}
                codes = [lookup[g] for g in self._collect_ids(value) if g in lookup]
                # "choose at least X" stores the threshold in `restriction`
                # (typically a credit-hour minimum for completedAtLeastXOf).
                choose_n = rule.get("restriction")
                requirements.append({
                    "group": group,
                    "condition": cond or "",
                    "courses": codes,
                    "choose_n": choose_n,
                    "note": "",
                })

        name = (data.get("name") or "").strip()
        degree = (data.get("degreeDesignation") or "").strip()
        display_name = f"{name} {degree}".strip() if degree and degree not in name else name

        return {
            "university": self.university,
            "program_id": program_id,
            "name": display_name,
            "degree": degree,
            "type": data.get("type") or "",
            "requirements": requirements,
        }
