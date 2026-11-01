import csv

import pytest

from src import compare, db
from src.analyse import Score
from tests.test_db import make_paper


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(compare, "ROOT", tmp_path)
    monkeypatch.setattr(compare, "SHEET", tmp_path / "hand_tags.csv")
    monkeypatch.setattr(compare, "SECOND_READER", tmp_path / "second_reader.csv")
    connection = db.connect()
    papers = [make_paper(f"{focus}{number}") for focus in ("em", "dm", "tv") for number in range(10)]
    db.save_papers(connection, papers)
    for paper in papers:
        focus = {"em": "EM", "dm": "DM", "tv": "Transversal"}[paper.id[:2]]
        db.save_analysis(connection, paper.id, "cheap", Score(summary="One.", market_focus=focus, tag_reason="why", relevance=7, topics=["rates"]))
    yield connection
    connection.close()


def sheet_rows():
    with open(compare.SHEET, newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def test_the_sheet_takes_more_em_papers(conn):
    compare.make_sheet()
    ids = [row["id"] for row in sheet_rows()]
    assert [sum(paper.startswith(focus) for paper in ids) for focus in ("em", "dm", "tv")] == [8, 6, 6]


def test_the_sheet_never_shows_the_ai_tag(conn):
    compare.make_sheet()
    assert list(sheet_rows()[0]) == ["id", "title", "abstract", "your_tag"]


def test_the_order_does_not_give_the_tag_away(conn):
    compare.make_sheet()
    prefixes = [row["id"][:2] for row in sheet_rows()]
    assert prefixes != sorted(prefixes)


def test_papers_already_tagged_are_skipped(conn):
    with open(compare.SECOND_READER, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["id", "tag"])
        writer.writerows([f"em{number}", "EM"] for number in range(5))
    compare.make_sheet()
    ids = {row["id"] for row in sheet_rows()}
    assert ids.isdisjoint({f"em{number}" for number in range(5)})


def test_the_same_database_gives_the_same_sheet(conn):
    compare.make_sheet()
    first = sheet_rows()
    compare.make_sheet()
    assert sheet_rows() == first


def test_score_compares_hand_tags_with_the_ai(conn, capsys):
    with open(compare.SHEET, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["id", "title", "abstract", "your_tag"])
        writer.writerow(["em0", "A paper", "An abstract.", "EM"])
        writer.writerow(["dm0", "Another", "An abstract.", "EM"])
    compare.score_sheet()
    output = capsys.readouterr().out
    assert "1 of 2 papers: 50%" in output
    assert "You: EM. AI: DM" in output
