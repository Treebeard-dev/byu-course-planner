# BYU Course Planner

A web app that gives a BYU student a tailored course plan for their **next two
semesters**, based on their major, target career or interests, and year in school.

> A learning project and portfolio piece, built with Claude Code by someone with
> no prior coding background.

## What it does

1. You enter your major, a target career or interests, and your year in school.
2. You get two semester columns of recommended courses, each with a one-line
   "why this course" reason.
3. You check off courses you've already taken, and the plan re-runs — a
   replacement appears, and courses that were locked behind a prerequisite can
   unlock.

Every recommendation is meant to be **defensible**: courses that satisfy your
major's requirements first, then electives and general-education courses chosen
to build the skills your target career actually needs.

**Scope:** BYU only. Next two semesters only. Not a replacement for an academic
advisor.

## How it's built

The guiding principle is **agents where judgment is needed, plain code where
correctness is needed**:

1. **Catalog scraper** — pulls BYU courses, credits, and prerequisites into a
   database.
2. **Career research agent** — builds a "skills map" for each career.
3. **Recommender** — fills your major's requirements, then ranks electives and
   GEs by the skills map.
4. **Validator** — deterministic checks for prerequisites, credits, and term
   availability.
5. **Web app** — a Streamlit interface.

**Stack:** Python · SQLite · Claude Agent SDK / Anthropic API · Streamlit · GitHub

## Status

🚧 In development — Phase 0 (setup). See `CLAUDE.md` for the full plan.

## Running it locally

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # macOS/Linux: .venv/bin/python

python fetch_courses.py byu              # pull the catalog (re-run each term to refresh)
python fetch_program.py byu accounting   # pull the Accounting BS requirements
python build_db.py                       # load everything into data/courses.db

python plan.py byu --program "Accounting BS" --year 2 --completed "ACC 200,WRTG 150"
python -m pytest -q
```

Example output (BYU sophomore): Winter finishes the pre-major plus *Logic & Critical
Thinking*; Fall starts the junior accounting core plus *Public Speaking*. Every
plan is checked by the validator for prerequisites, term availability, and credit
limits.
