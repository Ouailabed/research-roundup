from src import db, publish
from src.models import no_em_dash
from src.publish import clean_topics, site_data
from tests.test_db import RESULT, make_paper


def test_capitals_and_spaces_make_no_new_topic():
    assert clean_topics(["Inflation", " inflation "]) == ["inflation"]


def test_us_and_uk_spelling_are_one_topic():
    assert clean_topics(["labor markets", "labour markets"]) == ["labour markets"]


def test_near_names_are_one_topic():
    assert clean_topics(["Labor market", "artificial intelligence", "AI"]) == ["ai", "labour markets"]


def test_a_word_that_only_contains_labor_is_left_alone():
    assert clean_topics(["laboratory experiments"]) == ["laboratory experiments"]


def test_a_non_breaking_hyphen_makes_no_new_topic():
    assert clean_topics(["well" + chr(0x2011) + "being", "well-being"]) == ["well-being"]


def test_odd_hyphens_become_plain_ones_so_search_can_find_them():
    assert no_em_dash("long" + chr(0x2010) + "term pass" + chr(0x2011) + "through") == "long-term pass-through"


def site_with_pages(tmp_path, monkeypatch, *months):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(publish, "SITE", tmp_path)
    (tmp_path / "issues").mkdir()
    for month in months:
        (tmp_path / "issues" / f"{month}.html").write_text("page")
    return db.connect()


def test_each_issue_carries_its_opening_note(tmp_path, monkeypatch):
    conn = site_with_pages(tmp_path, monkeypatch, "2026-10")
    db.save_overview(conn, "2026-10", "a model", "Rates held the month together.")
    assert site_data(conn)["issues"] == [{"month": "2026-10", "file": "2026-10.html", "overview": "Rates held the month together."}]


def test_an_issue_with_no_opening_note_gets_an_empty_one(tmp_path, monkeypatch):
    conn = site_with_pages(tmp_path, monkeypatch, "2026-09")
    assert site_data(conn)["issues"][0]["overview"] == ""


def test_a_paper_is_only_in_issues_that_have_a_page(tmp_path, monkeypatch):
    conn = site_with_pages(tmp_path, monkeypatch, "2026-10")
    paper = make_paper("p1")
    db.save_papers(conn, [paper])
    db.save_analysis(conn, paper.id, "cheap", RESULT)
    db.save_issue(conn, "2026-09", [paper.id])
    db.save_issue(conn, "2026-10", [paper.id])
    assert site_data(conn)["papers"][0]["issues"] == ["2026-10"]
