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
1. **Picks their university first.** A student attends exactly one school, so
   this scopes everything that follows — a Utah student never sees BYU courses.
2. Enters major, target career or interests, and year (freshman–senior).
3. Sees two semester columns of recommended courses, each with a one-line
   "why this course" reason.
4. Checks off courses already taken. The plan re-runs: a replacement appears,
   and courses that needed the completed one as a prerequisite can unlock.

**Scoping rule (important):** every course is tagged with its university, and
every query, recommendation, and requirement is filtered to the selected school.
The data is multi-university; each *session* is single-university.

**Quality bar:** every recommendation must be defensible. No anatomy for an
accounting student, but a logic or ethics course that builds complementary
skills is welcome.

**Scope:** Build BYU end-to-end first, but design every data-facing piece to
**scale to many universities** (see "Data sources & scaling" below). Next two
semesters only. Not a replacement for an academic advisor.

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

## Data sources & scaling (confirmed in Phase 1 recon, 2026-09-26)

**Key finding:** university catalogs cluster onto a handful of vendor platforms.
Six target schools resolve to just **three platforms**. So we build one
**adapter per platform** (not per school); each new school is a small config
entry. This is the core scalability decision.

| School | Platform | Access | IDs / URLs |
|--------|----------|--------|-----------|
| BYU | Coursedog | JSON API | `schoolId=byu`, `catalogId=SDA0rZZwClSdh47nMnGv` |
| University of Utah | Coursedog | JSON API | `schoolId=utah_peoplesoft`, `catalogId=Qv3fMzzbHWUO6lkzqwgg` |
| Utah State (USU) | Coursedog | JSON API | `schoolId=usu` (banner-backed) |
| Boise State | Kuali | JSON API | host `boisestate.kuali.co`, `catalogId=68d5535c7e5bba5930769e2d` |
| Utah Valley (UVU) | CourseLeaf | HTML per subject | `catalog.uvu.edu/courses/<subj>/` (e.g. `/courses/acc/`) |
| Idaho State (ISU) | CourseLeaf | HTML per subject | `coursecat.isu.edu/...` |

### Coursedog (BYU, Utah, USU) — easiest
- Endpoint: `https://app.coursedog.com/api/v1/cm/<schoolId>/courses/search/$filters`
- Params: `catalogId`, `skip`/`limit` (paginate), `orderBy`, `columns` (comma
  list). BYU full catalog ≈ 7,969 courses.
- **Auth:** none, but gated by headers — send `Origin` and `Referer` set to the
  school's catalog host (a bare request returns 401). No `robots.txt` (404).
- Useful columns: `name`, `longName`, `subjectCode`, `courseNumber`, `code`,
  `credits.creditHours`, `description`, `college`, `departments`, `career`,
  `status`, `requisites`, `customFields.rawCourseId`.
- **Prerequisites:** structured under `requisites.requisitesSimple[]` (rule
  `type`, `condition` e.g. `completedAllOf`, `and`/`or`, list of required course
  IDs). Wrinkle: prereqs reference an internal course id (e.g. `"00011-009"`),
  not the code — pull all courses and build an id→code lookup.

### Kuali (Boise State) — easy
- All courses in one call: `https://<host>.kuali.co/api/v1/catalog/courses/<catalogId>`
  (returns a big JSON array; fields `__catalogCourseId`, `title`, `subjectCode`,
  `pid`, `id`).
- Per-course detail (incl. requisites): `.../catalog/course/<catalogId>/<pid>`.

### CourseLeaf / Modern Campus (UVU, ISU) — moderate
- No JSON API. Course data is well-structured HTML in `<div class="courseblock">`
  on per-subject pages, e.g. `catalog.uvu.edu/courses/<subj>/` (UVU Accounting
  page = 96 course blocks). Parse with BeautifulSoup. A per-course "ribbit"
  endpoint exists (`/ribbit/index.cgi?page=getcourse.rjs&code=...`) but needs
  exact codes.

**Etiquette (all platforms):** reasonable page sizes, a small delay between
requests, a clear User-Agent. Cache raw responses so re-runs don't re-hit.

### Adapter architecture
- `scrapers/base.py` — a `Course` shape + `CatalogAdapter` interface all
  adapters return (normalized: university, code, subject, number, title,
  credits, description, level, prerequisites, status, raw).
- `scrapers/coursedog.py`, `scrapers/kuali.py`, `scrapers/courseleaf.py` — one
  per platform (Coursedog built first; the others when needed).
- `universities.py` — registry mapping a school key (e.g. `byu`) to its platform
  + IDs/URLs.
- `fetch_courses.py` — CLI: `python fetch_courses.py byu --subject ACC`.

**Still to check:** term offerings (which terms a course is actually taught) —
often a separate source from the catalog.

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

## Product backlog / considerations (Alessandro's, to design for now, build later)

- **Analytics / metrics:** track what users search (major, career, year) and
  where they drop off, to learn demand and improve recommendations. Design the
  data model so events are easy to log later; actual dashboard is post-app.
- **Save progress:** let a user save their plan and completed-courses state and
  return to it (start with a shareable link or local save; accounts later).
- **Data freshness:** catalogs change slightly year over year. The scraper is
  **re-runnable per term** — that IS the refresh mechanism. Stamp each data pull
  with a fetch date + catalog year, and keep raw responses so we can diff.

## Conventions

- Language: Python. Keep code simple and readable over clever.
- Secrets live in `.env` (git-ignored). Never commit an API key.
- Data files live under `data/`.
- Prefer small, working increments over large rewrites.

## Current status

**Phase 1 — Scrape one department (building).** Recon done + multi-university
feasibility confirmed (3 platforms cover all 6 target schools; see "Data sources
& scaling"). Building the Coursedog adapter + `fetch_courses.py`; first output is
BYU Accounting (`ACC`) into `data/`, with prerequisite IDs resolved to codes.
Next platforms (Kuali, CourseLeaf) after BYU is proven end-to-end.

(Phase 0 complete except pasting the Anthropic API key into `.env`, which isn't
needed until Phase 3.)
