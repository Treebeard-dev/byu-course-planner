# CLAUDE.md — BYU Course Planner

This file is the handoff for Claude Code. Read it at the start of every session
before doing anything else.

## Who I am working with

Alessandro is building this as a **learning project** and a **portfolio piece**.
He has **no coding background**. That is the most important fact in this file.

Your job is not just to write code. Your job is to make him understand it.

## How to work with Alessandro

1. **Explain the plan in plain English before you build.** No jargon without a
   one-line definition the first time it appears.
2. **After you build, walk through what each file does**, line by line when it is
   new to him.
3. **Go one step at a time.** Do not run ahead multiple phases. Finish a step,
   show it working, then move on.
4. **When something breaks, explain _why_ it broke before fixing it.** The
   debugging is where the learning happens.
5. **Commit after every working step**, and have Alessandro write the commit
   message in his own words so he understands what changed.
6. **Prompt him to log new terms in `LEARNING.md`** in his own words as they come
   up.
7. **Keep the project plan doc's checkboxes in mind.** Remind him to tick off
   tasks as they are finished.

## What we are building

A web app that gives a BYU student a tailored course plan for their **next two
semesters**, based on their major, target career or interests, and year in
school.

The student:
1. Enters major, target career or interests, and year (freshman–senior).
2. Sees two semester columns of recommended courses, each with a one-line
   "why this course" reason.
3. Checks off courses already taken. The plan re-runs: a replacement appears,
   and courses that needed the completed one as a prerequisite can unlock.

**Quality bar:** every recommendation must be defensible. No anatomy for an
accounting student, but a logic or ethics course that builds complementary
skills is welcome.

**Scope:** BYU only. Next two semesters only. Not a replacement for an academic
advisor.

## Architecture

Guiding principle: **agents where judgment is needed, plain code where
correctness is needed.**

| # | Component | Type | Runs | Job |
|---|-----------|------|------|-----|
| 1 | Catalog scraper | Script + agent for messy pages | Once per term | Pull BYU courses, levels, credits, prerequisites, requirement mappings and term offerings into SQLite |
| 2 | Career research agent | Agent (Claude Agent SDK) | Offline, once per career | Build a skills map per career (e.g. Accountant: accounting core, data analysis, ethics, writing, logic) with sources |
| 3 | Recommender (orchestrator) | Agent + code | Per user request | Fill major requirement slots first, then rank electives and GEs by the skills map; return extra candidates for swaps |
| 4 | Validator | Deterministic code | Per user request | Check prerequisites, level vs. year (soft), credit load, term availability; drop anything that fails |
| 5 | Web app | Streamlit | Always | Input form, two semester columns, checkboxes that trigger a re-plan |

**Stack:** Python, SQLite, Claude Agent SDK / Anthropic API, Streamlit, GitHub.

**Open questions to check early:** whether BYU's catalog has an API or export
(it may run on Coursedog or Acalog), whether scraping is allowed (robots.txt and
terms), and where term offerings live, since the class schedule may be separate
from the catalog.

## Build phases

Each phase is a GitHub milestone. Commit after every working step.

- **Phase 0 — Setup:** tools, repo, first commit, the four docs, `.env`.
- **Phase 1 — Scrape one department:** find the catalog, check API/export and
  robots.txt, scrape Accounting into `data/courses.json`, spot-check 10 courses.
- **Phase 2 — Database:** design schema (courses, prerequisites, programs,
  requirements, offerings), load JSON into SQLite, add Accounting requirements,
  expand to GE + 2–3 more departments.
- **Phase 3 — Career research agent:** build with the Agent SDK, produce skills
  maps for 3–5 careers with sources into `data/skills_maps/*.json`, review by hand.
- **Phase 4 — Recommender and validator:** validator first, then recommender
  (requirement slots, then ranked electives/GEs with reasons), run from the CLI.
- **Phase 5 — Web app:** Streamlit form, two semester columns, checkboxes that
  re-plan.
- **Phase 6 — Evals and polish:** 10 test personas with pass/fail checks, README
  with diagram and screenshots, deploy to Streamlit Community Cloud.

**Expect friction in Phase 1.** Catalog sites are messy. Getting stuck there is
normal.

## Conventions

- Language: Python. Keep code simple and readable over clever.
- Secrets live in `.env` (git-ignored). Never commit an API key.
- Data files live under `data/`.
- Prefer small, working increments over large rewrites.

## Current status

**Phase 0 — Setup.** In progress.
