"""Look up a target job: "Did you mean...?" candidates, then its skill profile.

Examples:
    python job.py "auditor"
    python job.py "financial analyst" --pick 2
    python job.py "product manager" --codes 11-2021.00,11-3021.00
"""

from __future__ import annotations

import argparse
import sys

from outcomes import attribution, profile, search

TYPE_LABEL = {"knowledge": "knowledge", "skill": "skill", "cross-skill": "skill"}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Target job -> skills profile (O*NET).")
    ap.add_argument("job", help='what the student typed, e.g. "auditor"')
    ap.add_argument("--pick", type=int, default=1, help="which candidate to profile (1 = top)")
    ap.add_argument("--codes", default=None, help="comma-separated O*NET codes to blend instead")
    args = ap.parse_args()

    candidates = search(args.job)
    print(f'Did you mean ... ("{args.job}")')
    if not candidates:
        print("  no matches")
        return 1
    for i, c in enumerate(candidates, 1):
        flag = "" if c.rated else "  [no O*NET ratings yet]"
        via = f'  via "{c.matched_title}"' if c.matched_title != c.title else ""
        print(f"  {i}. {c.title} ({c.code}) score {c.score}{via}{flag}")

    codes = ([c.strip() for c in args.codes.split(",")] if args.codes
             else [candidates[min(args.pick, len(candidates)) - 1].code])
    p = profile(codes)
    print(f"\nProfile: {' + '.join(p.titles)}")
    print(f"Typical preparation: {p.education}")
    for n in p.notes:
        print(f"  note: {n}")
    if p.elements:
        print("Most important (O*NET importance, 1-5):")
        for e in p.elements:
            print(f"  {e.importance:4.2f}  {e.name} ({TYPE_LABEL[e.type]})")
    if p.tools:
        print("In-demand tools: " + ", ".join(p.tools))
    print(f"\nSource: {attribution()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
