"""Recommend (or check) a two-semester plan from the command line.

Recommend:
    python plan.py byu --program "Accounting BS" --year 2 --completed "ACC 200,WRTG 150"

Check a plan you wrote yourself:
    python plan.py byu --program "Accounting BS" --year 2 --completed "ACC 200" \
        --check "Winter 2027: ACC 310, ACC 402 | Fall 2027: ACC 401"
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from planner import Catalog, Student, Term, recommend, validate_plan

YEAR_NAMES = {1: "freshman", 2: "sophomore", 3: "junior", 4: "senior"}


def year_name(n: int) -> str:
    return YEAR_NAMES.get(n, "senior+" if n > 4 else "year " + str(n))


def parse_codes(text: str) -> list[str]:
    return [c.strip().upper() for c in text.split(",") if c.strip()]


def parse_check(text: str, catalog: Catalog) -> list[tuple[Term, list[str]]]:
    plan = []
    for chunk in text.split("|"):
        label, _, codes = chunk.partition(":")
        season, year = label.split()
        season = season.capitalize()
        month = catalog.semesters.get(season, 1)
        plan.append((Term(season, int(year), month), parse_codes(codes)))
    return plan


def print_issues(issues) -> None:
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    verdict = "VALID" if not errors else f"INVALID ({len(errors)} error(s))"
    print(f"\nValidation: {verdict}, {len(warnings)} warning(s)")
    for i in errors + warnings:
        mark = "x" if i.severity == "error" else "!"
        who = f"{i.code}: " if i.code else ""
        print(f"  [{mark}] {i.term}  {who}{i.message}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    ap = argparse.ArgumentParser(description="Plan the next two semesters.")
    ap.add_argument("university")
    ap.add_argument("--program", required=True, help='e.g. "Accounting BS"')
    ap.add_argument("--year", type=int, required=True, help="1=freshman ... 4=senior")
    ap.add_argument("--completed", default="", help="comma-separated course codes")
    ap.add_argument("--credits", type=int, default=15, help="target credits per semester")
    ap.add_argument("--today", default=None, help="YYYY-MM-DD (default: today)")
    ap.add_argument("--check", default=None, help='validate a plan: "Winter 2027: A, B | Fall 2027: C"')
    args = ap.parse_args()

    today = date.fromisoformat(args.today) if args.today else date.today()
    try:
        catalog = Catalog.from_db(args.university.lower())
        student = Student(args.university.lower(), args.program, args.year,
                          set(parse_codes(args.completed)), args.credits)
        catalog.program(student.program)
    except (KeyError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    done = ", ".join(sorted(student.completed)) or "nothing yet"
    print(f"{catalog.name} | {student.program} | {year_name(student.year)} | completed: {done}")

    if args.check:
        issues = validate_plan(catalog, student, parse_check(args.check, catalog), today)
        print_issues(issues)
        return 0 if not any(i.severity == "error" for i in issues) else 2

    result = recommend(catalog, student, today)
    for tp in result.terms:
        print(f"\n{tp.term.label.upper()}  ({year_name(tp.standing)}, {tp.credits:g} credits)")
        for p in tp.picks:
            print(f"  {p.code:<10} {p.title[:44]:<44} {p.credits:>4g}  {p.kind.upper()}")
            print(f"  {'':<10} why: {p.reason}")
        if tp.alternates:
            alts = ", ".join(f"{a.code} ({a.title[:28]})" for a in tp.alternates)
            print(f"  swap options: {alts}")

    print_issues(result.issues)
    if result.program_notes:
        print("\nProgram rules to know (not checked automatically):")
        for n in result.program_notes:
            print("  - " + " ".join(n.split()))
    if result.still_required:
        print(f"\nStill required after these two semesters ({len(result.still_required)}): "
              + ", ".join(result.still_required))
    print("\nPlanning guidance only. Confirm with your academic advisor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
