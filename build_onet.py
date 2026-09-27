"""Condense the raw O*NET downloads into one compact, committable file.

Reads data/onet/*.csv (from fetch_onet.py) and writes data/onet_occupations.json:
  - the 68 knowledge/skill "elements" every occupation is rated on
  - per occupation: title, description, job zone, alternate job titles,
    importance + level for each element, and in-demand software

Attribution (required by CC BY 4.0): this file is derived from the O*NET 31.0
Database by the U.S. Department of Labor, Employment and Training Administration
(USDOL/ETA), used under CC BY 4.0. Modified: filtered, reshaped, and summarized.

Usage:
    python build_onet.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

RAW = Path(__file__).parent / "data" / "onet"
OUT = Path(__file__).parent / "data" / "onet_occupations.json"

ATTRIBUTION = (
    "This product includes information from the O*NET 31.0 Database by the U.S. "
    "Department of Labor, Employment and Training Administration (USDOL/ETA). Used "
    "under the CC BY 4.0 license (https://creativecommons.org/licenses/by/4.0/). "
    "O*NET is a trademark of USDOL/ETA. Modified: filtered, reshaped, and summarized."
)

RATING_FILES = {
    "knowledge": "knowledge.csv",
    "skill": "essential_skills.csv",          # basic skills (2.A.*)
    "cross-skill": "transferable_skills.csv", # cross-functional skills (2.B.*)
}

JOB_ZONES = {
    "1": "little or no preparation",
    "2": "some preparation (high school)",
    "3": "medium preparation (vocational training or associate's degree)",
    "4": "considerable preparation (usually a bachelor's degree)",
    "5": "extensive preparation (usually a graduate degree)",
}


def rows(name: str):
    with open(RAW / name, encoding="utf-8", newline="") as fh:
        yield from csv.DictReader(fh)


def main() -> None:
    occupations: dict[str, dict] = {}
    for r in rows("occupation_data.csv"):
        occupations[r["O*NET-SOC Code"]] = {
            "title": r["Title"],
            "description": r["Description"],
            "job_zone": None,
            "titles": [],
            "ratings": {},     # element_id -> [importance, level]
            "tools": [],
        }

    for r in rows("job_titles.csv"):
        occ = occupations.get(r["O*NET-SOC Code"])
        if occ is not None and r["Job Title"] not in occ["titles"]:
            occ["titles"].append(r["Job Title"])

    for r in rows("job_zones.csv"):
        if r["O*NET-SOC Code"] in occupations:
            occupations[r["O*NET-SOC Code"]]["job_zone"] = int(r["Job Zone"])

    elements: dict[str, dict] = {}
    for kind, fname in RATING_FILES.items():
        for r in rows(fname):
            occ = occupations.get(r["O*NET-SOC Code"])
            if occ is None or r["Recommend Suppress"] == "Y" or r["Not Relevant"] == "Y":
                continue
            eid = r["Element ID"]
            elements.setdefault(eid, {"id": eid, "name": r["Element Name"], "type": kind})
            slot = occ["ratings"].setdefault(eid, [None, None])
            value = round(float(r["Data Value"]), 2)
            if r["Scale ID"] == "IM":
                slot[0] = value
            elif r["Scale ID"] == "LV":
                slot[1] = value

    # Only software O*NET marks as in demand for that occupation (from job
    # postings). This drops noise like hospital systems listed for accountants.
    for r in rows("software_skills.csv"):
        occ = occupations.get(r["O*NET-SOC Code"])
        if occ is not None and r["In Demand"] == "Y" and r["Workplace Example"] not in occ["tools"]:
            occ["tools"].append(r["Workplace Example"])

    # Some occupations have titles but no ratings yet in this O*NET release
    # (e.g. Financial and Investment Analysts). Keep them so a search still
    # finds the right job; the profile step handles the missing ratings openly.
    for o in occupations.values():
        o["rated"] = bool(o["ratings"])

    OUT.write_text(json.dumps({
        "source": "O*NET 31.0 Database",
        "attribution": ATTRIBUTION,
        "job_zones": JOB_ZONES,
        "elements": sorted(elements.values(), key=lambda e: e["id"]),
        "occupations": occupations,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    n_rated = sum(o["rated"] for o in occupations.values())
    n_titles = sum(len(o["titles"]) for o in occupations.values())
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)")
    print(f"  {len(elements)} elements, {len(occupations)} occupations "
          f"({n_rated} rated), {n_titles:,} alternate titles")


if __name__ == "__main__":
    main()
