"""Registry of universities and how to reach each one's catalog.

Adding a new school is just a new entry here — no new scraping code, as long as
its platform already has an adapter. That is the whole point of the adapter
design: the hard part (talking to a platform) is written once.
"""

from __future__ import annotations

from scrapers import CoursedogAdapter

# Each entry says which platform a school uses and the ids/urls that identify it.
UNIVERSITIES: dict[str, dict] = {
    "byu": {
        "name": "Brigham Young University",
        "platform": "coursedog",
        "school_id": "byu",
        "catalog_id": "SDA0rZZwClSdh47nMnGv",
        "catalog_host": "https://catalog.byu.edu",
        # Planning rules. "semesters" = the main terms and the month each starts;
        # BYU's Spring/Summer are short optional terms, so they aren't planned.
        "semesters": {"Winter": 1, "Fall": 9},
        "full_time_credits": 12,
        "max_credits": 18,
    },
    "utah": {
        "name": "University of Utah",
        "platform": "coursedog",
        "school_id": "utah_peoplesoft",
        "catalog_id": "Qv3fMzzbHWUO6lkzqwgg",
        "catalog_host": "https://catalog.utah.edu",
        "semesters": {"Spring": 1, "Fall": 8},
        "full_time_credits": 12,
        "max_credits": 18,
    },
    "usu": {
        "name": "Utah State University",
        "platform": "coursedog",
        "school_id": "usu",
        "catalog_id": "",   # TODO: confirm USU catalogId (banner-backed)
        "catalog_host": "https://catalog.usu.edu",
        "semesters": {"Spring": 1, "Fall": 8},
        "full_time_credits": 12,
        "max_credits": 18,
    },
    # --- other platforms, adapters to be added later ---
    # "boisestate": {"platform": "kuali", ...},
    # "uvu":        {"platform": "courseleaf", ...},
    # "isu":        {"platform": "courseleaf", ...},
}


# Known degree programs we want requirements for, per school.
# (program ids come from each catalog's programs API)
PROGRAMS: dict[str, dict[str, dict]] = {
    "byu": {
        "accounting": {"id": "34574-2026-09-02", "name": "Accounting BS"},
    },
    # "utah": {"accounting": {"id": "...", "name": "Accounting BS"}},
}


def get_adapter(university_key: str):
    """Build the right adapter for a school key like 'byu'."""
    key = university_key.lower()
    if key not in UNIVERSITIES:
        raise KeyError(
            f"Unknown university '{university_key}'. "
            f"Known: {', '.join(sorted(UNIVERSITIES))}"
        )
    cfg = UNIVERSITIES[key]
    platform = cfg["platform"]

    if platform == "coursedog":
        if not cfg.get("catalog_id"):
            raise ValueError(f"'{key}' has no catalog_id set yet.")
        return CoursedogAdapter(
            university=key,
            school_id=cfg["school_id"],
            catalog_id=cfg["catalog_id"],
            catalog_host=cfg["catalog_host"],
        )

    raise NotImplementedError(
        f"No adapter for platform '{platform}' yet (school '{key}')."
    )
