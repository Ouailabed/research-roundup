import pytest

from src import db
from src.analyse import Score
from src.models import Paper


def make_paper(paper_id, abstract="An abstract.", first_seen="2026-10-05"):
    return Paper(
        id=paper_id,
        title=f"Paper {paper_id}",
        authors="A. Author",
        abstract=abstract,
        url=f"https://example.org/{paper_id}",
        doi="",
        source="NBER",
        group="research_body",
        published="",
        first_seen=first_seen,
        fetched_at="2026-10-05T00:00:00+00:00",
    )


RESULT = Score(summary="One. Two.", market_focus="DM", tag_reason="names the US", relevance=7, topics=["rates"])


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    connection = db.connect()
    yield connection
    connection.close()


def test_second_save_adds_no_new_papers(conn):
    papers = [make_paper("a"), make_paper("b")]
    assert db.save_papers(conn, papers) == 2
    assert db.save_papers(conn, papers) == 0


def test_analysed_papers_are_not_analysed_again(conn):
    db.save_papers(conn, [make_paper("a"), make_paper("b")])
    db.save_analysis(conn, "a", "cheap", RESULT)
    assert [row["id"] for row in db.papers_to_analyse(conn, "2026-09-01")] == ["b"]


def test_a_paper_scored_by_any_model_is_not_scored_again(conn):
    db.save_papers(conn, [make_paper("a")])
    db.save_analysis(conn, "a", "another cheap model", RESULT)
    assert db.papers_to_analyse(conn, "2026-09-01") == []


def test_papers_with_no_abstract_are_left_out(conn):
    db.save_papers(conn, [make_paper("a", abstract="")])
    assert db.papers_to_analyse(conn, "2026-09-01") == []


def test_old_papers_are_left_out(conn):
    db.save_papers(conn, [make_paper("a", first_seen="2026-08-30")])
    assert db.papers_to_analyse(conn, "2026-09-01") == []


def test_saved_issue_keeps_its_order(conn):
    db.save_issue(conn, "2026-10", ["c", "a", "b"])
    assert db.saved_issue(conn, "2026-10") == ["c", "a", "b"]


def test_candidates_come_from_that_month_only(conn):
    db.save_papers(conn, [make_paper("a"), make_paper("b", first_seen="2026-09-05")])
    db.save_analysis(conn, "a", "cheap", RESULT)
    db.save_analysis(conn, "b", "cheap", RESULT)
    assert [row["id"] for row in db.issue_candidates(conn, "2026-10")] == ["a"]
