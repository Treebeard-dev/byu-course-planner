"""Fetch a university's courses and save them as JSON.

Examples:
    python fetch_courses.py byu --subject ACC
    python fetch_courses.py byu                 # whole catalog
    python fetch_courses.py utah --subject ACCTG
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from universities import get_adapter, UNIVERSITIES

DATA_DIR = Path(__file__).parent / "data"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch university course data.")
    parser.add_argument(
        "university",
        help=f"school key ({', '.join(sorted(UNIVERSITIES))})",
    )
    parser.add_argument(
        "--subject", "-s", default=None,
        help="limit to one subject code, e.g. ACC",
    )
    parser.add_argument(
        "--out", "-o", default=None,
        help="output file (default: data/<school>_<subject|all>_courses.json)",
    )
    args = parser.parse_args()

    try:
        adapter = get_adapter(args.university)
    except (KeyError, ValueError, NotImplementedError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    label = args.subject.upper() if args.subject else "all"
    print(f"Fetching {args.university} courses ({label})... this pulls the full "
          f"catalog once to resolve prerequisites, so give it a few seconds.")

    courses = adapter.fetch_courses(subject=args.subject)
    courses.sort(key=lambda c: (c.subject, c.number))

    DATA_DIR.mkdir(exist_ok=True)
    out_path = (
        Path(args.out) if args.out
        else DATA_DIR / f"{args.university}_{label.lower()}_courses.json"
    )
    payload = {
        "university": args.university,
        "subject": args.subject,
        "count": len(courses),
        "courses": [c.to_dict() for c in courses],
    }
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                        encoding="utf-8")

    print(f"Saved {len(courses)} courses -> {out_path}")
    with_prereqs = sum(1 for c in courses if c.prerequisites)
    print(f"  ({with_prereqs} have resolved prerequisites)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
