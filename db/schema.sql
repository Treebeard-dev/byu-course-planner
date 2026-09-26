-- BYU Course Planner — database schema
--
-- Design rule: the data holds many universities, but a student session is always
-- ONE university. So `university` is on every table and part of the uniqueness
-- constraints, and every app query filters by it. Schools never mix.

PRAGMA foreign_keys = ON;

-- The schools we have data for.
CREATE TABLE IF NOT EXISTS universities (
    key      TEXT PRIMARY KEY,      -- e.g. "byu", "utah"
    name     TEXT NOT NULL,         -- e.g. "University of Utah"
    platform TEXT                   -- e.g. "coursedog"
);

-- One row per course, scoped to a university.
CREATE TABLE IF NOT EXISTS courses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    university   TEXT NOT NULL REFERENCES universities(key),
    code         TEXT NOT NULL,     -- e.g. "ACC 200"
    subject      TEXT,              -- e.g. "ACC"
    number       TEXT,              -- e.g. "200"
    title        TEXT,
    credits      REAL,              -- nominal credit hours
    credits_min  REAL,              -- set only when credits are variable
    credits_max  REAL,
    level        INTEGER,           -- school-native: 200 (BYU) or 2100 (Utah)
    year_level   INTEGER,           -- normalized standing: 1=fr..4=sr, 5+=grad
    description  TEXT,
    college      TEXT,
    department   TEXT,
    career       TEXT,
    status       TEXT,
    source_id    TEXT,              -- platform's internal id (provenance)
    fetched_at   TEXT,              -- when the data was pulled
    catalog_year TEXT,
    -- Identity is the platform's own id, NOT the code: "topic" courses share one
    -- code across many distinct classes (e.g. MUSIC 360R = Cello, Bass, ...).
    UNIQUE (university, source_id)
);

CREATE INDEX IF NOT EXISTS idx_courses_uni_code    ON courses (university, code);
CREATE INDEX IF NOT EXISTS idx_courses_uni_subject ON courses (university, subject);
CREATE INDEX IF NOT EXISTS idx_courses_uni_level   ON courses (university, level);

-- The prerequisite graph: "course_code requires prereq_code" (one edge per row).
-- (For now this is a flat AND-list; and/or nuance can be layered on later.)
CREATE TABLE IF NOT EXISTS prerequisites (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    university  TEXT NOT NULL REFERENCES universities(key),
    course_code TEXT NOT NULL,      -- the course that has the requirement
    prereq_code TEXT NOT NULL,      -- one course it requires
    UNIQUE (university, course_code, prereq_code)
);

CREATE INDEX IF NOT EXISTS idx_prereq_uni_course ON prerequisites (university, course_code);

-- Forward-looking (populated in a later step): degree programs and what they
-- require. Kept here so the schema is complete and the loader can grow into it.
CREATE TABLE IF NOT EXISTS programs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    university  TEXT NOT NULL REFERENCES universities(key),
    name        TEXT NOT NULL,      -- e.g. "Accounting BS"
    degree_type TEXT,               -- e.g. major / minor / GE
    UNIQUE (university, name)
);

CREATE TABLE IF NOT EXISTS program_requirements (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id        INTEGER NOT NULL REFERENCES programs(id),
    requirement_group TEXT,         -- e.g. "Requirement 1", "Core"
    condition         TEXT,         -- e.g. completedAllOf / completedAtLeastXOf / note
    course_code       TEXT,         -- a candidate/required course (nullable for notes)
    choose_n          INTEGER,      -- for "choose N from this group"
    notes             TEXT          -- freeform rule text (grades, timing, ...)
);

CREATE INDEX IF NOT EXISTS idx_progreq_program ON program_requirements (program_id);
