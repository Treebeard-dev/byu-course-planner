"""Tests for the prerequisite logic, schedule parsing, validator and recommender.

Run:  python -m pytest -q
The first groups use tiny hand-built data; the last group runs against the real
database and is skipped if it hasn't been built.
"""

from datetime import date

import pytest

from planner import Catalog, Student, Term, next_semesters, offered_in, recommend, validate_plan
from planner.catalog import CourseInfo, DB_PATH, Program, RequirementGroup
from scrapers.base import class_year_from_number, tree_satisfied, tree_text

TODAY = date(2026, 9, 26)
WINTER = Term("Winter", 2027, 1)
FALL = Term("Fall", 2027, 9)


# --- prerequisite trees -------------------------------------------------------

def test_any_of_needs_only_one():
    tree = {"op": "any", "items": ["ACC 305", "ACC 310"]}
    assert tree_satisfied(tree, {"ACC 310"})
    assert not tree_satisfied(tree, {"ACC 200"})


def test_nested_all_and_any():
    tree = {"op": "all", "items": ["A 1", {"op": "any", "items": ["B 1", "C 1"]}]}
    assert tree_satisfied(tree, {"A 1", "C 1"})
    assert not tree_satisfied(tree, {"A 1"})
    assert tree_text(tree) == "A 1 and (B 1 or C 1)"


def test_at_least_n():
    tree = {"op": "atleast", "n": 2, "items": ["A 1", "B 1", "C 1"]}
    assert tree_satisfied(tree, {"A 1", "C 1"})
    assert not tree_satisfied(tree, {"A 1"})


def test_no_prereqs_always_satisfied():
    assert tree_satisfied(None, set())


def test_year_level_is_comparable_across_schools():
    assert class_year_from_number("200") == class_year_from_number("2100") == 2
    assert class_year_from_number("310R") == 3


# --- schedules ----------------------------------------------------------------

@pytest.mark.parametrize("text,term,expected", [
    ("Fall and Winter", WINTER, True),
    ("Winter", FALL, False),
    ("All Semesters/Terms", FALL, True),
    ("Contact Department", FALL, None),
    ("", FALL, None),
    ("Winter Odd Years", WINTER, True),           # 2027 is odd
    ("Winter Even Years", WINTER, False),
    ("Fall and Winter; Spring: Contact Department", FALL, True),
    ("Fall and Winter; Spring: Contact Department", Term("Spring", 2027, 4), None),
    ("Fall; Winter.", WINTER, True),
])
def test_offered_in(text, term, expected):
    assert offered_in(text, term) is expected


def test_next_two_semesters_per_school():
    byu = next_semesters(TODAY, {"Winter": 1, "Fall": 9})
    utah = next_semesters(TODAY, {"Spring": 1, "Fall": 8})
    assert [t.label for t in byu] == ["Winter 2027", "Fall 2027"]
    assert [t.label for t in utah] == ["Spring 2027", "Fall 2027"]


# --- validator on a tiny fake catalog ----------------------------------------

def tiny_catalog() -> Catalog:
    c = {
        "A 100": CourseInfo("A 100", "Intro", 3.0, 1, offered="Fall and Winter"),
        "A 200": CourseInfo("A 200", "Next", 3.0, 2, offered="Fall",
                            tree={"op": "any", "items": ["A 100", "X 100"]}),
        "A 300": CourseInfo("A 300", "Winter only", 3.0, 3, offered="Winter"),
        "B 100": CourseInfo("B 100", "Unknown schedule", 3.0, 1, offered="Contact Department"),
        "G 500": CourseInfo("G 500", "Grad", 3.0, 5, offered="Fall and Winter"),
    }
    prog = Program("Test BS", [RequirementGroup("Core", "completedAllOf", ["A 100", "A 200"])])
    cat = Catalog("testu", c, {"Test BS": prog})
    cat.semesters = {"Winter": 1, "Fall": 9}
    return cat


def errors(issues):
    return [(i.code, i.message.split()[0]) for i in issues if i.severity == "error"]


def test_prereq_must_be_in_an_earlier_term():
    cat, s = tiny_catalog(), Student("testu", "Test BS", 1)
    same_term = validate_plan(cat, s, [(FALL, ["A 100", "A 200"])], TODAY)
    assert ("A 200", "Prerequisites") in errors(same_term)
    earlier = validate_plan(cat, s, [(WINTER, ["A 100"]), (FALL, ["A 200"])], TODAY)
    assert not any(code == "A 200" for code, _ in errors(earlier))


def test_wrong_season_is_an_error_unknown_is_a_warning():
    cat, s = tiny_catalog(), Student("testu", "Test BS", 3)
    issues = validate_plan(cat, s, [(FALL, ["A 300", "B 100"])], TODAY)
    assert ("A 300", "Not") in errors(issues)
    assert any(i.code == "B 100" and i.severity == "warning" for i in issues)


def test_completed_duplicate_and_credit_limit():
    cat = tiny_catalog()
    s = Student("testu", "Test BS", 1, completed={"A 100"}, max_credits=5)
    issues = validate_plan(cat, s, [(WINTER, ["A 100", "B 100"])], TODAY)
    assert ("A 100", "Already") in errors(issues)
    assert any(i.code == "" and "limit" in i.message for i in issues)


def test_graduate_course_warns_undergrad():
    cat, s = tiny_catalog(), Student("testu", "Test BS", 3)
    issues = validate_plan(cat, s, [(WINTER, ["G 500"])], TODAY)
    assert any(i.code == "G 500" and "Graduate" in i.message for i in issues)


def test_student_and_catalog_must_match():
    with pytest.raises(ValueError):
        recommend(tiny_catalog(), Student("byu", "Test BS", 1), TODAY)


# --- recommender on the real database -----------------------------------------

needs_db = pytest.mark.skipif(not DB_PATH.exists(), reason="run build_db.py first")


@needs_db
@pytest.mark.parametrize("year,completed", [
    (1, set()),
    (2, {"ACC 200", "WRTG 150"}),
    (3, {"ACC 200", "ACC 310", "IS 201", "ACC 241", "FIN 201"}),
])
def test_recommended_plans_are_valid(year, completed):
    cat = Catalog.from_db("byu")
    result = recommend(cat, Student("byu", "Accounting BS", year, completed), TODAY)
    assert [t.term.label for t in result.terms] == ["Winter 2027", "Fall 2027"]
    assert not [i for i in result.issues if i.severity == "error"]
    for tp in result.terms:
        assert tp.credits <= cat.max_credits
        assert any(p.kind == "breadth" for p in tp.picks), "every semester gets breadth"
        codes = [p.code for p in tp.picks]
        assert len(codes) == len(set(codes))
        assert not (set(codes) & completed)


@needs_db
def test_sophomore_finishes_premajor_before_fall_major_courses():
    cat = Catalog.from_db("byu")
    r = recommend(cat, Student("byu", "Accounting BS", 2, {"ACC 200", "WRTG 150"}), TODAY)
    winter = {p.code for p in r.terms[0].picks}
    assert {"IS 201", "ACC 310"} <= winter
    assert not any("Requirement 3" in s for s in r.still_required)


@needs_db
def test_universities_never_mix():
    byu, utah = Catalog.from_db("byu"), Catalog.from_db("utah")
    assert byu.get("ACCTG 2100") is None
    assert utah.get("ACC 200") is None
