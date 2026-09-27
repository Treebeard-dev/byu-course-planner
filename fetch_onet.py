"""Download the O*NET files we use into data/onet/ (git-ignored; re-runnable).

Source: O*NET 31.0 Database, U.S. Department of Labor, Employment and Training
Administration. Licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).
We modify it (filter and summarize it per occupation) for this project.

Usage:
    python fetch_onet.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests

VERSION = "31_0"
BASE = f"https://www.onetcenter.org/dl_files/database/db_{VERSION}_csv/"
FILES = [
    "occupation_data.csv",
    "job_titles.csv",
    "knowledge.csv",
    "essential_skills.csv",
    "transferable_skills.csv",
    "software_skills.csv",
    "job_zones.csv",
]
OUT_DIR = Path(__file__).parent / "data" / "onet"


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers["User-Agent"] = "byu-course-planner/0.1 (student project; GitHub Treebeard-dev)"
    for name in FILES:
        target = OUT_DIR / name
        resp = session.get(BASE + name, timeout=120)
        if resp.status_code != 200:
            print(f"  FAILED {name}: HTTP {resp.status_code}", file=sys.stderr)
            return 1
        target.write_bytes(resp.content)
        print(f"  {name:<26} {len(resp.content) / 1e6:6.2f} MB")
    print(f"Saved to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
