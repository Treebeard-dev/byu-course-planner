"""Baseline (rules-only) recommender for the next two semesters.

For each semester, in order:
  1. Required courses the student is eligible for, most "unlocking" first: a
     course that other required courses depend on goes before one that doesn't,
     so the student isn't blocked later (critical-path ordering).
  2. Choose-N elective groups from the major, until their minimum is met.
  3. Breadth courses (see complements.py), at least one per semester, filling
     up to the target load but never past the credit limit.

"Eligible" = not done, prerequisites completed in an earlier term, taught that
term (or schedule unknown), and not more than one year above the student's
standing. The finished plan is run through the validator as a self-check.

This is deliberately simple. It's the baseline the Phase 3 agent must beat.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from scrapers.base import tree_codes, tree_satisfied
from .catalog import Catalog, RequirementGroup
from .complements import complements_for
from .models import Pick, PlanResult, Student, TermPlan
from .terms import Term, next_semesters, offered_in, standing_for
from .validator import validate_plan


def _group_need(group: RequirementGroup, have: set[str], catalog: Catalog) -> float:
    """How much of a choose-N group is still unmet (courses, or credits when the
    catalog's threshold is bigger than the number of options)."""
    taken = [c for c in group.courses if c in have]
    n = group.choose_n or 1
    if n > len(group.courses):   # threshold is in credits
        got = sum((catalog.get(c).credits or 0) for c in taken if catalog.get(c))
        return max(0.0, n - got)
    return max(0, n - len(taken))


def _critical_weight(catalog: Catalog, required: list[str]) -> dict[str, int]:
    """For each required course: how many other required courses need it,
    directly or through a chain of prerequisites."""
    req = set(required)

    def ancestors(code: str, seen: set[str]) -> set[str]:
        course = catalog.get(code)
        for p in tree_codes(course.tree if course else None):
            if p not in seen:
                seen.add(p)
                ancestors(p, seen)
        return seen

    weight = {c: 0 for c in required}
    for r in required:
        for a in ancestors(r, set()):
            if a in weight and a != r:
                weight[a] += 1
    return weight


def recommend(catalog: Catalog, student: Student, today: Optional[date] = None,
              n_terms: int = 2, breadth_per_term: int = 1,
              n_alternates: int = 3) -> PlanResult:
    today = today or date.today()
    if student.university != catalog.university:
        raise ValueError("Student and catalog are from different universities.")
    program = catalog.program(student.program)
    max_credits = student.max_credits or catalog.max_credits
    target = min(student.target_credits, max_credits)
    terms = next_semesters(today, catalog.semesters, n_terms)

    required = [c for g in program.groups if not g.is_choose
                for c in g.courses if catalog.get(c)]
    required = list(dict.fromkeys(required))                  # dedupe, keep order
    required_set = set(required)
    weight = _critical_weight(catalog, required)
    choose_groups = [g for g in program.groups if g.is_choose]
    breadth = complements_for(catalog.university, student.program)

    done = set(student.completed)       # completed before the current term
    planned: set[str] = set()
    plan: list[TermPlan] = []

    for term in terms:
        standing = standing_for(student.year, term, today)
        tp = TermPlan(term, standing)
        reserve = 3 * breadth_per_term  # keep room for breadth

        def eligible(code: str) -> bool:
            c = catalog.get(code)
            if not c or c.credits is None or code in done or code in planned:
                return False
            if not tree_satisfied(c.tree, done):
                return False
            if offered_in(c.offered, term) is False:
                return False
            return not (c.year_level and c.year_level > standing + 1)

        def take(code: str, kind: str, reason: str) -> None:
            c = catalog.get(code)
            if offered_in(c.offered, term) is None:
                reason += " (Schedule not published: confirm it runs this term.)"
            tp.picks.append(Pick(code, c.title, c.credits, kind, reason))
            planned.add(code)

        # 1+2. requirement groups IN CATALOG ORDER (pre-major before major core),
        # choose-N groups at their place in that order. Within a group, the most
        # "unlocking" course goes first.
        budget = target - reserve
        for g in program.groups:
            if g.is_choose:
                by_credits = (g.choose_n or 1) > len(g.courses)
                while _group_need(g, done | planned, catalog) > 0:
                    # Prefer: schedule published for this term, then (for credit
                    # thresholds) bigger courses so the group finishes sooner,
                    # then lower level.
                    options = sorted(
                        (c for c in g.courses if eligible(c)),
                        key=lambda c: (offered_in(catalog.get(c).offered, term) is not True,
                                       -(catalog.get(c).credits or 0) if by_credits else 0,
                                       catalog.get(c).year_level or 9, c))
                    fits = [c for c in options
                            if tp.credits + catalog.get(c).credits <= budget]
                    if not fits:
                        break
                    take(fits[0], "elective",
                         f"Counts toward {g.name} of {program.name} (choose from "
                         f"{', '.join(g.courses)}).")
                continue
            for code in sorted((c for c in g.courses if c in required_set and eligible(c)),
                               key=lambda c: (-weight[c], catalog.get(c).year_level or 9, c)):
                if tp.credits + catalog.get(code).credits > budget:
                    continue
                opens = sorted(catalog.unlocks(code) & required_set)
                reason = f"Required for {program.name} ({g.name})."
                if opens:
                    reason += (f" Unlocks {', '.join(opens[:3])}"
                               + (" and more." if len(opens) > 3 else "."))
                take(code, "required", reason)

        # 3. breadth: prefer courses with a published schedule for this term
        options = [(c, why) for c, why in breadth if eligible(c)]
        options.sort(key=lambda cw: offered_in(catalog.get(cw[0]).offered, term) is not True)
        added = 0
        for code, why in options:
            credits = catalog.get(code).credits
            if tp.credits + credits > max_credits:
                continue
            if added >= breadth_per_term and tp.credits + credits > target:
                continue
            take(code, "breadth", why)
            added += 1

        # alternates, for swaps: the next eligible required/elective/breadth options
        pool = [c for c in required if eligible(c)] + \
               [c for g in choose_groups for c in g.courses if eligible(c)] + \
               [c for c, _ in breadth if eligible(c)]
        for code in list(dict.fromkeys(pool))[:n_alternates]:
            c = catalog.get(code)
            kind = "required" if code in required_set else \
                   "breadth" if code in dict(breadth) else "elective"
            tp.alternates.append(Pick(code, c.title, c.credits, kind,
                                      dict(breadth).get(code, "Also eligible this term.")))

        plan.append(tp)
        done |= {p.code for p in tp.picks}

    issues = validate_plan(catalog, student,
                           [(t.term, [p.code for p in t.picks]) for t in plan], today)

    still = [c for c in required if c not in done]
    for g in choose_groups:
        need = _group_need(g, done, catalog)
        if need:
            unit = "credits" if (g.choose_n or 1) > len(g.courses) else "course(s)"
            still.append(f"{need:g} more {unit} from {g.name} ({', '.join(g.courses)})")

    return PlanResult(
        student=student,
        terms=plan,
        issues=issues,
        program_notes=program.notes,
        still_required=still,
    )
