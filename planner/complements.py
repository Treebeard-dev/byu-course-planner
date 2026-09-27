"""Complementary ("breadth") courses per program.

BASELINE ONLY: this list is hand-picked from the real catalog so the rules-based
recommender has something defensible to suggest. In Phase 3 the career-research
agent replaces it with skills maps generated per career, with sources. Keeping
the hand-picked version gives us a baseline to measure the agent against.

Each entry: (course code, why it helps this student).
"""

from __future__ import annotations

COMPLEMENTS: dict[str, dict[str, list[tuple[str, str]]]] = {
    "byu": {
        "Accounting BS": [
            ("PHIL 205", "Logic and critical thinking: the structured reasoning that "
                         "audit and analysis work depends on."),
            ("STDEV 150", "Public speaking: accountants who can present clearly to "
                          "clients and executives stand out."),
            ("IS 115", "Python for data analytics: automation is reshaping accounting "
                       "work, and data skills keep you ahead of it."),
            ("ENGL 323", "Professional writing: clear memos and reports are a core "
                         "client-facing skill."),
            ("PHIL 213", "Ethics: a grounding for a profession built on trust and "
                         "judgment calls."),
            ("STAT 121", "Statistics: the basis of audit sampling and analytics-driven "
                         "accounting."),
            ("MSB 315", "Negotiation: useful in client work, fee discussions, and "
                        "career moves."),
            ("PSYCH 111", "Psychology: understanding how people decide, useful for "
                          "management and spotting fraud risk."),
            ("ENT 323", "Sales and persuasion: builds the business-development side "
                        "that partners value."),
            ("C S 110", "Programming basics: a practical edge as accounting tools "
                        "automate."),
        ],
    },
}


def complements_for(university: str, program: str) -> list[tuple[str, str]]:
    return COMPLEMENTS.get(university, {}).get(program, [])
