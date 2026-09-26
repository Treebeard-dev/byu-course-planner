"""Fetch a degree program's requirements and save them as JSON.

Course-list requirements are resolved to real course codes; grade/timing/other
freeform rules are kept as notes (we plan, we don't run a full degree audit).

Examples:
    python fetch_program.py byu accounting
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from universities import get_adapter, PROGRAMS

DATA_DIR = Path(__file__).parent / "data"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch a program's requirements.")
    parser.add_argument("university", help="school key, e.g. byu")
    parser.add_argument("program", help="program key from PROGRAMS, e.g. accounting")
    args = parser.parse_args()

    progs = PROGRAMS.get(args.university.lower(), {})
    if args.program.lower() not in progs:
        print(f"Error: no program '{args.program}' for '{args.university}'. "
              f"Known: {', '.join(progs) or '(none)'}", file=sys.stderr)
        return 1
    prog = progs[args.program.lower()]

    adapter = get_adapter(args.university)
    if not hasattr(adapter, "fetch_program"):
        print(f"Error: {adapter.platform} adapter can't fetch programs yet.",
              file=sys.stderr)
        return 1

    print(f"Fetching {args.university} program '{prog['name']}' "
          f"(id {prog['id']})...")
    result = adapter.fetch_program(prog["id"])

    DATA_DIR.mkdir(exist_ok=True)
    out_path = DATA_DIR / f"{args.university}_{args.program.lower()}_program.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False),
                        encoding="utf-8")

    reqs = result["requirements"]
    course_rules = [r for r in reqs if r["courses"]]
    note_rules = [r for r in reqs if r["condition"] == "note"]
    print(f"Saved -> {out_path}")
    print(f"  {len(reqs)} requirement rules "
          f"({len(course_rules)} course-list, {len(note_rules)} notes)")
    for r in course_rules[:8]:
        print(f"    [{r['group']}] {r['condition']}: {', '.join(r['courses'][:8])}"
              + (" ..." if len(r["courses"]) > 8 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
