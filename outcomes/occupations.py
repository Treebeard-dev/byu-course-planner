"""Target job -> O*NET occupation(s) -> the knowledge and skills that job needs.

Two parts:

  search(query)   "Did you mean...?" candidates for what the student typed. We
                  never silently pick one: typed job titles are ambiguous
                  ("financial analyst" is also an alternate title under
                  Statisticians), so the student confirms.

  profile(codes)  The confirmed job's most important knowledge and skills, from
                  O*NET importance ratings (1-5; 3+ = "important"). Several codes
                  can be blended for jobs O*NET doesn't model directly (e.g.
                  "product manager").

Data: data/onet_occupations.json (built by build_onet.py from O*NET 31.0,
USDOL/ETA, CC BY 4.0).
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "onet_occupations.json"

# Common shorthand students type. Heuristic and deliberately small; unknown
# jargon is a job for the AI step later.
ABBREVIATIONS = {
    "cpa": "certified public accountant",
    "fp&a": "financial planning and analysis",
    "swe": "software engineer",
    "sde": "software engineer",
    "pm": "product manager",
    "hr": "human resources",
    "ux": "user experience",
    "ui": "user interface",
    "qa": "quality assurance",
    "rn": "registered nurse",
    "cfo": "chief financial officer",
    "ceo": "chief executive officer",
    "cto": "chief technology officer",
    "ml": "machine learning",
    "it": "information technology",
}
# Words that describe seniority or employer, not the job itself, plus filler.
NOISE = {"senior", "sr", "junior", "jr", "entry", "level", "lead", "principal",
         "intern", "internship", "trainee", "i", "ii", "iii", "big", "4", "four",
         "and", "&", "of", "the", "for", "in", "or"}
# Word families that should match each other (manager ~ management).
FAMILIES = {"manag": ("manager", "management", "managing"),
            "analy": ("analyst", "analysis", "analytics", "analytical"),
            "account": ("accountant", "accounting"),
            "engineer": ("engineering",),
            "develop": ("developer", "development")}
_FAMILY_OF = {w: root for root, words in FAMILIES.items() for w in words}


def _stem(tok: str) -> str:
    tok = tok[:-1] if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss") else tok
    return _FAMILY_OF.get(tok, tok)


def normalize(text: str) -> tuple[str, ...]:
    """Lowercase, expand abbreviations, drop noise words, singularize."""
    toks = re.findall(r"[a-z0-9&+#]+", text.lower())
    expanded: list[str] = []
    for t in toks:
        expanded.extend(ABBREVIATIONS.get(t, t).split())
    return tuple(_stem(t) for t in expanded if t not in NOISE)


@dataclass
class Candidate:
    code: str
    title: str
    score: float
    matched_title: str      # the O*NET title that matched best
    rated: bool             # False = O*NET has no ratings for it yet


@dataclass
class Element:
    id: str
    name: str
    type: str               # knowledge | skill | cross-skill
    importance: float       # 1-5
    level: Optional[float]  # 0-7, how advanced


@dataclass
class JobProfile:
    codes: list[str]
    titles: list[str]
    elements: list[Element]             # important ones, most important first
    tools: list[str]                    # in-demand software
    job_zone: Optional[int]
    education: str
    notes: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def _load() -> dict:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"{DATA_PATH} not found - run fetch_onet.py and build_onet.py.")
    data = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    index = []
    for code, occ in data["occupations"].items():
        primary = normalize(occ["title"])
        alts = [(normalize(t), t) for t in occ["titles"]]
        index.append((code, occ, primary, alts))
    data["_index"] = index
    data["_elements"] = {e["id"]: e for e in data["elements"]}
    return data


def attribution() -> str:
    return _load()["attribution"]


def search(query: str, n: int = 5) -> list[Candidate]:
    """Best-matching occupations for a typed job title, best first."""
    q = normalize(query)
    if not q:
        return []
    qs = set(q)
    results: list[Candidate] = []
    for code, occ, primary, alts in _load()["_index"]:
        # How many of this occupation's titles contain every query word: a
        # popularity signal that breaks ties toward the job's "home" occupation.
        containing = [raw for toks, raw in alts if qs <= set(toks)]
        popularity = min(10.0, 2 * math.log2(1 + len(containing)))
        exact_alt = [raw for toks, raw in alts if toks == q]

        # A match on the occupation's own title beats one on an alternate title.
        if primary == q:
            score, matched = 100.0, occ["title"]
        elif qs <= set(primary):
            score, matched = 88.0 - 2 * len(set(primary) - qs), occ["title"]
        elif exact_alt:
            score, matched = 85.0, exact_alt[0]
        elif containing:
            score, matched = 60.0, min(containing, key=len)
        else:
            best, matched = 0.0, ""
            for toks, raw in [(primary, occ["title"])] + alts:
                s = set(toks)
                if s:
                    j = len(qs & s) / len(qs | s)
                    if j > best:
                        best, matched = j, raw
            score = 50.0 * best
        # Tie-breaker: prefer occupations whose main title shares the query's
        # words ("certified public accountant" -> Accountants and Auditors,
        # not Tax Preparers, even though both list it as an alternate title).
        ps = set(primary)
        overlap = 5.0 * len(qs & ps) / len(qs | ps) if ps else 0.0
        if score > 0:
            results.append(Candidate(code, occ["title"], round(score + popularity + overlap, 1),
                                     matched, occ["rated"]))
    results.sort(key=lambda c: -c.score)
    return results[:n]


def profile(codes: list[str], min_importance: float = 3.0,
            max_elements: int = 15) -> JobProfile:
    """Blend the important knowledge/skills of one or more occupations."""
    data = _load()
    occs = data["occupations"]
    unknown = [c for c in codes if c not in occs]
    if unknown:
        raise KeyError(f"Unknown O*NET code(s): {', '.join(unknown)}")

    notes: list[str] = []
    rated = [c for c in codes if occs[c]["rated"]]
    for c in codes:
        if not occs[c]["rated"]:
            notes.append(f"O*NET has not published skill ratings for "
                         f"'{occs[c]['title']}' yet, so it can't shape the profile.")
    if len(codes) > 1:
        notes.append("Blended from: " + "; ".join(occs[c]["title"] for c in codes) + ".")

    elements: list[Element] = []
    if rated:
        eids = {eid for c in rated for eid in occs[c]["ratings"]}
        for eid in eids:
            # Average across the blended jobs; a job that doesn't rate an
            # element counts as O*NET's minimum importance (1).
            ims = [(occs[c]["ratings"].get(eid) or [1, None])[0] or 1 for c in rated]
            lvs = [(occs[c]["ratings"].get(eid) or [None, None])[1] for c in rated]
            lvs = [v for v in lvs if v is not None]
            im = sum(ims) / len(ims)
            if im >= min_importance:
                meta = data["_elements"][eid]
                elements.append(Element(eid, meta["name"], meta["type"], round(im, 2),
                                        round(sum(lvs) / len(lvs), 2) if lvs else None))
        # O*NET rates a few things twice (e.g. Mathematics as knowledge AND as a
        # skill). Show each name once, keeping the higher rating.
        elements.sort(key=lambda e: -e.importance)
        seen: set[str] = set()
        elements = [e for e in elements if not (e.name in seen or seen.add(e.name))]
        elements = elements[:max_elements]

    tools: list[str] = []
    for c in codes:
        for t in occs[c]["tools"]:
            if t not in tools:
                tools.append(t)

    zones = [occs[c]["job_zone"] for c in codes if occs[c]["job_zone"]]
    zone = max(zones) if zones else None
    return JobProfile(
        codes=list(codes),
        titles=[occs[c]["title"] for c in codes],
        elements=elements,
        tools=tools,
        job_zone=zone,
        education=data["job_zones"].get(str(zone), "unknown") if zone else "unknown",
        notes=notes,
    )
