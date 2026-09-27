"""Tests for target-job matching and O*NET job profiles.

Skipped if data/onet_occupations.json hasn't been built (fetch_onet.py + build_onet.py).
"""

import pytest

from outcomes.occupations import DATA_PATH, normalize

pytestmark = pytest.mark.skipif(not DATA_PATH.exists(), reason="run build_onet.py first")


def top(query):
    from outcomes import search
    return search(query, 3)[0].title


def test_normalize_handles_noise_plurals_and_abbreviations():
    assert normalize("Senior Auditors") == ("auditor",)
    assert normalize("Big 4 auditor") == ("auditor",)
    assert normalize("CPA") == ("certified", "public", "account")
    assert normalize("manager") == normalize("management")


@pytest.mark.parametrize("query,expected", [
    ("auditor", "Accountants and Auditors"),
    ("Big 4 auditor", "Accountants and Auditors"),
    ("CPA", "Accountants and Auditors"),
    ("financial analyst", "Financial and Investment Analysts"),
    ("project manager", "Project Management Specialists"),
    ("data scientist", "Data Scientists"),
    ("software engineer", "Software Developers"),
    ("management consultant", "Management Analysts"),
    ("lawyer", "Lawyers"),
])
def test_common_jobs_match(query, expected):
    assert top(query) == expected


def test_search_offers_alternatives_and_flags_unrated():
    from outcomes import search
    results = search("financial analyst", 5)
    assert len(results) == 5
    fia = next(c for c in results if c.title == "Financial and Investment Analysts")
    assert fia.rated is False


def test_auditor_profile_is_sensible():
    from outcomes import profile
    p = profile(["13-2011.00"])
    names = [e.name for e in p.elements]
    assert names[0] == "Economics and Accounting"
    assert {"Writing", "Critical Thinking", "Speaking", "Law and Government"} <= set(names)
    assert len(names) == len(set(names)), "each element shown once"
    assert all(e.importance >= 3.0 for e in p.elements)
    assert "Microsoft Excel" in p.tools
    assert not any("Epic" in t or "MEDITECH" in t for t in p.tools), "hospital software filtered"
    assert p.job_zone == 4


def test_unrated_job_says_so_instead_of_guessing():
    from outcomes import profile
    p = profile(["13-2051.00"])
    assert p.elements == []
    assert any("not published" in n for n in p.notes)


def test_blended_profile():
    from outcomes import profile
    p = profile(["11-2021.00", "11-3021.00"])
    assert len(p.titles) == 2 and p.elements
    assert any("Blended" in n for n in p.notes)


def test_unknown_code_raises():
    from outcomes import profile
    with pytest.raises(KeyError):
        profile(["99-9999.99"])
