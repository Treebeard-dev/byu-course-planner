# CLAUDE.md — BYU Course Planner

This file is the handoff for Claude Code. Read it at the start of every session
before doing anything else.

## Who I am working with

Alessandro is building this to **ship a portfolio piece for PM (product manager)
internship applications**. He has **no coding background** and does not need to
become an engineer.

What matters for his goal, in priority order:
1. A **working, demoable, deployed** product with a shareable link.
2. **Product decisions and trade-offs he can defend in an interview** (scope
   cuts, the "agents vs. code" split, the quality bar, what he'd do next).
3. A clear **build story**: the problem, the user, how he directed AI agents,
   what worked and what didn't.

Deep, line-by-line code mastery is **not** a goal. Explain at the level he'd need
to talk about the project confidently in an interview, not to write the code by
hand.

## How to work with Alessandro

1. **Ship first.** Bias toward a working increment over a perfect explanation.
   Keep momentum toward a deployed demo.
2. **Explain at "interview altitude."** Enough that he understands what a
   component does and *why it was built that way* — the decision and the
   trade-off — not every line of syntax.
3. **Capture product decisions as they happen.** When a real choice comes up
   (scope, build-vs-buy, agent-vs-code, a cut), name it, note the trade-off, and
   flag it as interview/portfolio material.
4. **Go one meaningful step at a time.** Finish a step, show it working, commit,
   then move on.
5. **When something breaks, give the short "why" then fix it** and keep moving.
6. **Commit after every working step** with a clear message.
7. **Log new terms in `LEARNING.md` lightly as they come up.** Alessandro wants a
   single **batch glossary review at the end** (it doubles as interview prep) —
   do not stop the build to define every term in the moment.
8. **Keep the project plan doc's checkboxes updated** as tasks finish.

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

## Data source (confirmed in Phase 1 recon, 2026-09-26)

BYU's catalog (`catalog.byu.edu`) runs on **Coursedog** and is backed by a
**public JSON API** — no HTML scraping needed.

- **Course search endpoint:**
  `https://app.coursedog.com/api/v1/cm/byu/courses/search/$filters`
- **School id:** `byu` · **Catalog id:** `SDA0rZZwClSdh47nMnGv`
- **Params:** `skip`/`limit` (paginate), `orderBy`, `columns` (comma-list of
  fields), `catalogId`. Full catalog is **~7,969 courses**.
- **Auth:** none, but the API is gated by headers — send
  `Origin: https://catalog.byu.edu` and `Referer: https://catalog.byu.edu/`
  (a bare request returns 401). No `robots.txt` at either host (both 404).
  Be polite: reasonable page sizes, small delay between requests.
- **Useful columns:** `name`, `longName`, `subjectCode` (e.g. `ACC` for
  Accounting), `courseNumber`, `code`, `credits.creditHours`, `description`,
  `college`, `departments`, `career`, `status`, `requisites`,
  `customFields.rawCourseId`, `customFields.crseOfferNbr`.
- **Prerequisites:** structured, under `requisites.requisitesSimple[]` (rule
  `type`, `condition` like `completedAllOf`, `and`/`or` logic, and a list of
  required course IDs). **Wrinkle:** prereqs reference courses by an internal id
  (e.g. `"00011-009"`), not by code — pull all courses and build an id→code
  lookup to resolve them.
- **Data hygiene:** filter to `status == "Active"` and drop obvious test rows
  (e.g. names containing "Test").
- **Still to check:** where term offerings live (which terms a course is
  actually taught) — the class schedule may be a separate source from the
  catalog (BYU has an official Developer Portal API for schedules, but it needs
  OAuth credentials).

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

**Phase 1 — Scrape one department.** Recon done: found the Coursedog JSON API
(see "Data source" above), confirmed access and that prerequisites are available.
Next: write the Python fetcher to pull Accounting (`ACC`) courses into
`data/courses.json` and resolve prerequisite IDs to codes.

(Phase 0 complete except pasting the Anthropic API key into `.env`, which isn't
needed until Phase 3.)
