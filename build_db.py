"""Build the SQLite database from the fetched JSON course files.

Reads every data/*_courses.json file, and loads courses + prerequisites into a
single SQLite database (data/courses.db), tagged by university. Safe to re-run:
it rebuilds from scratch each time, so it doubles as the "refresh" step.

Usage:
    python build_db.py
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from universities import UNIVERSITIES

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "courses.db"
SCHEMA_PATH = ROOT / "db" / "schema.sql"


def load_course_files() -> list[dict]:
    """Every fetched course file, e.g. byu_acc_courses.json."""
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(DATA_DIR.glob("*_courses.json"))
    ]


def load_program_files() -> list[dict]:
    """Every fetched program file, e.g. byu_accounting_program.json."""
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(DATA_DIR.glob("*_program.json"))
    ]


def build() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()   # rebuild fresh

    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    files = load_course_files()
    seen_universities: set[str] = set()
    n_courses = n_prereqs = 0

    for payload in files:
        uni = payload["university"]

        if uni not in seen_universities:
            cfg = UNIVERSITIES.get(uni, {})
            conn.execute(
                "INSERT OR IGNORE INTO universities (key, name, platform) VALUES (?, ?, ?)",
                (uni, cfg.get("name", uni), cfg.get("platform", "")),
            )
            seen_universities.add(uni)

        for c in payload["courses"]:
            cur = conn.execute(
                """INSERT OR IGNORE INTO courses
                   (university, code, subject, number, title, credits,
                    credits_min, credits_max, level, year_level, description,
                    college, department, career, status, source_id, fetched_at,
                    catalog_year)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (uni, c["code"], c["subject"], c["number"], c["title"],
                 c["credits"], c["credits_min"], c["credits_max"], c["level"],
                 c["year_level"], c["description"], c["college"], c["department"],
                 c["career"], c["status"], c["source_id"], c["fetched_at"],
                 c["catalog_year"]),
            )
            n_courses += cur.rowcount   # 0 when a duplicate was ignored

            for prereq in c["prerequisites"]:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO prerequisites
                       (university, course_code, prereq_code) VALUES (?,?,?)""",
                    (uni, c["code"], prereq),
                )
                n_prereqs += cur.rowcount

    # -- programs & their requirements ---------------------------------------
    n_programs = n_reqrows = 0
    for prog in load_program_files():
        uni = prog["university"]
        cur = conn.execute(
            "INSERT OR IGNORE INTO programs (university, name, degree_type) VALUES (?,?,?)",
            (uni, prog["name"], prog.get("degree") or prog.get("type") or ""),
        )
        row = conn.execute(
            "SELECT id FROM programs WHERE university=? AND name=?",
            (uni, prog["name"]),
        ).fetchone()
        program_id = row[0]
        n_programs += 1

        for req in prog["requirements"]:
            group = req.get("group")
            cond = req.get("condition")
            choose_n = req.get("choose_n")
            note = req.get("note") or ""
            courses = req.get("courses") or []
            if courses:
                for code in courses:
                    conn.execute(
                        """INSERT INTO program_requirements
                           (program_id, requirement_group, condition, course_code,
                            choose_n, notes) VALUES (?,?,?,?,?,?)""",
                        (program_id, group, cond, code, choose_n, ""),
                    )
                    n_reqrows += 1
            else:  # a freeform note rule
                conn.execute(
                    """INSERT INTO program_requirements
                       (program_id, requirement_group, condition, course_code,
                        choose_n, notes) VALUES (?,?,?,?,?,?)""",
                    (program_id, group, cond, None, None, note),
                )
                n_reqrows += 1

    conn.commit()

    # quick report
    print(f"Built {DB_PATH}")
    for row in conn.execute(
        "SELECT university, COUNT(*) FROM courses GROUP BY university ORDER BY university"
    ):
        print(f"  {row[0]}: {row[1]} courses")
    print(f"  total courses: {n_courses}, prerequisite edges: {n_prereqs}")
    print(f"  programs: {n_programs}, requirement rows: {n_reqrows}")
    conn.close()


if __name__ == "__main__":
    build()
