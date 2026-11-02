import json
from datetime import date
from types import SimpleNamespace

import pytest

from src import db, issue
from src.analyse import Analysis, DailyLimitReached, Overview, Ranking
from tests.test_db import RESULT, make_paper
from src.issue import choose_papers, date_label, editor_order, issue_context, last_full_month, months_since, no_em_dash

ROWS = [
    ("a", "NBER", "DM", 9),
    ("b", "NBER", "DM", 9),
    ("c", "NBER", "DM", 8),
    ("d", "IMF", "EM", 6),
    ("e", "BIS", "Transversal", 7),
    ("f", "IMF", "EM", 5),
    ("g", "ECB", "DM", 8),
    ("h", "ECB", "DM", 7),
    ("i", "ECB", "DM", 6),
    ("j", "BoE", "DM", 7),
    ("k", "BoE", "DM", 7),
]


def test_same_papers_always_give_the_same_issue():
    assert choose_papers(ROWS) == choose_papers(list(reversed(ROWS)))


def test_at_most_8_papers():
    assert len(choose_papers(ROWS)) == 8


def test_at_most_2_per_source():
    chosen = choose_papers(ROWS)
    sources = [row[1] for row in ROWS if row[0] in chosen]
    assert max(sources.count(source) for source in sources) <= 2


def test_every_focus_is_included_when_it_exists():
    chosen = choose_papers(ROWS)
    focuses = {row[2] for row in ROWS if row[0] in chosen}
    assert focuses == {"EM", "DM", "Transversal"}


def test_highest_score_comes_first():
    assert choose_papers(ROWS)[0] == "a"


def paper_row(number, source=None, focus="DM", score=9):
    return {
        "id": f"p{number:03d}",
        "source": source or f"Source {number}",
        "market_focus": focus,
        "relevance": score,
        "title": f"Paper {number}",
        "summary": "It finds something.",
    }


class Editor:
    """Stands in for Groq. Each call lists the papers it was shown, and it ranks them with its choice of rule."""

    def __init__(self, choose):
        self.choose = choose
        self.calls = []
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        shown = kwargs["messages"][1]["content"].split("\n\n")
        self.calls.append(len(shown))
        answer = json.dumps({"ranking": self.choose(shown)})
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=answer))])


def last_first(shown):
    return list(range(len(shown), 0, -1))


def test_the_editor_order_replaces_the_score():
    rows = [paper_row(number) for number in range(1, 13)]
    chosen = choose_papers(editor_order(rows, "model", Editor(last_first)))
    assert len(chosen) == 8
    # Every paper tied on score, so without the editor the lowest ids would have won.
    assert chosen != [row["id"] for row in rows[:8]]


def test_the_rules_still_apply_to_the_editor_order():
    rows = [paper_row(number, source="NBER") for number in range(1, 13)]
    rows += [paper_row(number, focus="EM", score=5) for number in range(13, 19)]
    chosen = choose_papers(editor_order(rows, "model", Editor(last_first)))
    picked = [row for row in rows if row["id"] in chosen]
    assert sum(row["source"] == "NBER" for row in picked) == 2
    assert any(row["market_focus"] == "EM" for row in picked)


def test_a_long_list_goes_through_in_groups():
    rows = [paper_row(number) for number in range(1, 86)]
    editor = Editor(last_first)
    editor_order(rows, "model", editor)
    # 85 papers make 3 groups of up to 40, then the winners are ranked together.
    assert editor.calls == [40, 40, 5, 21]


def test_numbers_the_editor_made_up_are_ignored():
    rows = [paper_row(number) for number in range(1, 13)]
    order = editor_order(rows, "model", Editor(lambda shown: [99, 0, 3, 3, *last_first(shown)]))
    assert len([row for row in order if row[3] > -500]) == 12


def test_a_short_ranking_is_asked_for_again():
    rows = [paper_row(number) for number in range(1, 13)]
    answers = iter([[1], list(range(12, 0, -1))])
    editor = Editor(lambda shown: next(answers))
    order = editor_order(rows, "model", editor)
    assert editor.calls == [12, 12]
    assert len([row for row in order if row[3] > -500]) == 12


def test_two_short_rankings_mean_the_plain_scores_decide(capsys):
    rows = [paper_row(number) for number in range(1, 13)]
    assert editor_order(rows, "model", Editor(lambda shown: [1])) == rows
    assert "plain scores" in capsys.readouterr().out


def test_no_usable_answer_means_the_plain_scores_decide(monkeypatch, capsys):
    rows = [paper_row(number) for number in range(1, 13)]
    monkeypatch.setattr(issue, "checked_answer", lambda *args: None)
    assert editor_order(rows, "model", Editor(last_first)) == rows
    assert "plain scores" in capsys.readouterr().out


def test_the_editor_waits_out_the_daily_limit(monkeypatch, capsys):
    rows = [paper_row(number) for number in range(1, 13)]
    naps = []
    answers = iter([DailyLimitReached("the model has used up today's allowance", 110), Ranking(ranking=list(range(12, 0, -1)))])

    def next_answer(*args):
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(issue, "checked_answer", next_answer)
    monkeypatch.setattr(issue.time, "sleep", naps.append)
    order = editor_order(rows, "model", Editor(last_first))
    assert naps == [110]
    assert len([row for row in order if row[3] > -500]) == 12


def test_an_issue_with_no_opening_note_yet_is_finished_on_a_later_run(month_of_papers, monkeypatch):
    monkeypatch.setattr(issue, "have_key", lambda: False)
    db.save_issue(month_of_papers, "2026-10", ["p0"])

    def limit(*args):
        raise DailyLimitReached("the model has used up today's allowance")

    monkeypatch.setattr(issue, "write_up", lambda *args: True)
    monkeypatch.setattr(issue, "issue_papers", lambda *args: [])
    monkeypatch.setattr(issue, "write_overview", limit)
    assert issue.build_issue("2026-10") is issue.STOPPED
    assert not issue.is_finished(month_of_papers, "2026-10")


def test_no_key_means_the_plain_scores_decide():
    rows = [paper_row(number) for number in range(1, 13)]
    assert editor_order(rows, "model", None) == rows


def test_a_quiet_month_needs_no_editor():
    rows = [paper_row(number) for number in range(1, 8)]
    editor = Editor(last_first)
    assert editor_order(rows, "model", editor) == rows
    assert editor.calls == []


@pytest.fixture
def month_of_papers(monkeypatch, tmp_path):
    """A database with no key, holding 8 scored papers from 8 sources in October."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(issue, "have_key", lambda: False)
    monkeypatch.setattr(issue, "ISSUE_FOLDER", tmp_path / "issues")
    conn = db.connect()
    papers = [make_paper(f"p{number}", source=f"Source {number}") for number in range(8)]
    db.save_papers(conn, papers)
    for paper in papers:
        db.save_analysis(conn, paper.id, "cheap", RESULT)
    yield conn
    conn.close()


def test_an_issue_waits_while_many_papers_are_unscored(month_of_papers, capsys):
    db.save_papers(month_of_papers, [make_paper(f"new{number}") for number in range(6)])
    assert issue.build_issue("2026-10") is None
    assert db.saved_issue(month_of_papers, "2026-10") == []
    assert "6 papers still to score" in capsys.readouterr().out


def test_a_few_stuck_papers_do_not_hold_up_an_issue(month_of_papers):
    db.save_papers(month_of_papers, [make_paper(f"new{number}") for number in range(5)])
    issue.build_issue("2026-10")
    assert len(db.saved_issue(month_of_papers, "2026-10")) == 8


WRITTEN = Analysis(summary="One.", market_focus="DM", tag_reason="names Japan", relevance=7, topics=["rates"], takeaways=["a", "b", "c"], why_it_matters="It matters.")


def finish(conn, month, paper_id):
    """Saves everything a finished month has."""
    db.save_issue(conn, month, [paper_id])
    db.save_writeup(conn, paper_id, "model", WRITTEN)
    db.save_overview(conn, month, "model", "A note.")
    issue.ISSUE_FOLDER.mkdir(exist_ok=True)
    (issue.ISSUE_FOLDER / f"{month}.html").write_text("done")


def test_a_finished_month_is_not_built_again(month_of_papers, monkeypatch):
    built = []
    monkeypatch.setattr(issue, "build_issue", built.append)
    monkeypatch.setattr(issue, "last_full_month", lambda: "2026-10")
    finish(month_of_papers, "2026-09", "p0")
    db.save_issue(month_of_papers, "2026-10", ["p1"])
    issue.build_missing_issues()
    # September is finished. October has a list but nothing else, because its run stopped halfway.
    assert built == ["2026-10"]


def test_a_month_chosen_again_is_not_finished_by_its_old_page(month_of_papers):
    finish(month_of_papers, "2026-10", "p0")
    assert issue.is_finished(month_of_papers, "2026-10")
    db.clear_issue(month_of_papers, "2026-10")
    db.save_issue(month_of_papers, "2026-10", ["p1"])
    assert not issue.is_finished(month_of_papers, "2026-10")


def test_a_month_waiting_for_its_opening_note_is_not_finished(month_of_papers):
    finish(month_of_papers, "2026-10", "p0")
    month_of_papers.execute("DELETE FROM overviews")
    assert not issue.is_finished(month_of_papers, "2026-10")


def test_a_month_with_a_page_but_no_list_is_chosen_again(month_of_papers, monkeypatch):
    built = []
    monkeypatch.setattr(issue, "build_issue", built.append)
    monkeypatch.setattr(issue, "last_full_month", lambda: "2026-09")
    issue.ISSUE_FOLDER.mkdir()
    (issue.ISSUE_FOLDER / "2026-09.html").write_text("an older version")
    issue.build_missing_issues()
    assert built == ["2026-09"]


def writer(monkeypatch, failing):
    """Stands in for the model, with no valid answer for the papers named."""
    written = Analysis(summary="One.", market_focus="DM", tag_reason="names Japan", relevance=7, topics=["rates"], takeaways=["a", "b", "c"], why_it_matters="It matters.")
    monkeypatch.setattr(issue, "have_key", lambda: True)
    monkeypatch.setattr(issue, "groq_client", lambda: None)
    monkeypatch.setattr(issue, "analyse_paper", lambda client, model, paper, shape: None if paper["id"] in failing else written)


def test_a_paper_that_keeps_failing_leaves_the_issue_and_the_rest_go_on(month_of_papers, monkeypatch):
    writer(monkeypatch, {"p2"})
    chosen = [f"p{number}" for number in range(8)]
    db.save_issue(month_of_papers, "2026-10", chosen)
    assert issue.write_up(month_of_papers, "2026-10", chosen, "model")
    assert "p2" not in db.saved_issue(month_of_papers, "2026-10")
    assert db.has_writeup(month_of_papers, "p7")


def test_too_few_write_ups_means_the_month_is_chosen_again(month_of_papers, monkeypatch):
    writer(monkeypatch, {f"p{number}" for number in range(4)})
    chosen = [f"p{number}" for number in range(8)]
    db.save_issue(month_of_papers, "2026-10", chosen)
    assert not issue.write_up(month_of_papers, "2026-10", chosen, "model")
    assert db.saved_issue(month_of_papers, "2026-10") == []


def test_the_daily_limit_stops_the_later_months_too(month_of_papers, monkeypatch):
    months = []

    def build(month):
        months.append(month)
        return issue.STOPPED

    monkeypatch.setattr(issue, "build_issue", build)
    monkeypatch.setattr(issue, "last_full_month", lambda: "2026-10")
    monkeypatch.setattr(issue, "load_settings", lambda: {"analyse_from": "2026-09-01"})
    issue.build_missing_issues()
    assert months == ["2026-09"]


def test_work_left_counts_papers_and_unfinished_issues(month_of_papers, monkeypatch):
    monkeypatch.setattr(issue, "last_full_month", lambda: "2026-10")
    monkeypatch.setattr(issue, "load_settings", lambda: {"analyse_from": "2026-09-01"})
    db.save_papers(month_of_papers, [make_paper("new")])
    finish(month_of_papers, "2026-10", "p0")
    # One paper to score, plus September, which has no issue yet.
    assert issue.work_left() == 2


def test_no_work_left_means_zero(month_of_papers, monkeypatch):
    monkeypatch.setattr(issue, "last_full_month", lambda: "2026-10")
    monkeypatch.setattr(issue, "load_settings", lambda: {"analyse_from": "2026-10-01"})
    finish(month_of_papers, "2026-10", "p0")
    assert issue.work_left() == 0


def test_an_opening_note_is_written_once_and_saved(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(issue, "have_key", lambda: True)
    monkeypatch.setattr(issue, "groq_client", lambda: None)
    answers = iter([Overview(overview="Rates matter \u2014 a lot.")])
    monkeypatch.setattr(issue, "checked_answer", lambda *args: next(answers))
    conn = db.connect()
    papers = [{"title": "A paper", "market_focus": "DM", "summary": "It finds something."}]
    assert issue.write_overview(conn, "2026-10", papers, "model") == "Rates matter, a lot."
    # A second call would raise StopIteration if it asked the model again.
    assert issue.write_overview(conn, "2026-10", papers, "model") == "Rates matter, a lot."
    conn.close()


def test_an_issue_builds_without_an_opening_note(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(issue, "have_key", lambda: True)
    monkeypatch.setattr(issue, "groq_client", lambda: None)
    monkeypatch.setattr(issue, "checked_answer", lambda *args: None)
    conn = db.connect()
    assert issue.write_overview(conn, "2026-10", [], "model") == ""
    conn.close()


def test_the_opening_note_shows_only_when_there_is_one():
    paper = {
        "title": "A paper", "authors": "A. Author", "source": "NBER", "url": "https://example.org", "published_label": "3 October 2026",
        "market_focus": "DM", "summary": "It finds something.", "takeaways": ["a", "b", "c"], "why_it_matters": "It matters.", "tag_reason": "It names Japan.",
    }
    assert "Rates matter." in issue.render_issue("2026-10", [paper], 10, 2, "Rates matter.")
    assert 'class="count"' in issue.render_issue("2026-10", [paper], 10, 2)


def test_last_full_month():
    assert last_full_month(date(2026, 11, 1)) == "2026-10"
    assert last_full_month(date(2026, 1, 15)) == "2025-12"


def test_months_since_crosses_a_year():
    assert months_since("2026-11-01", "2027-02") == ["2026-11", "2026-12", "2027-01", "2027-02"]


def test_date_labels():
    assert date_label("2026-10-03") == "3 October 2026"
    assert date_label("2026-10") == "October 2026"
    assert date_label("2026") == "2026"


def test_a_future_date_is_not_shown():
    row = {
        "title": "A paper",
        "published": "2026-11-05",
        "first_seen": "2026-10-31",
        "summary": "One.",
        "takeaways": '["a", "b", "c"]',
        "why_it_matters": "It matters.",
        "tag_reason": "It names Peru.",
    }
    assert issue_context([row])[0]["published_label"] == "31 October 2026"


def test_em_dashes_are_removed():
    assert no_em_dash("Rates \u2014 and more") == "Rates, and more"
