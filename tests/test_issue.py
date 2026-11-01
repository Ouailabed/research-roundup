import json
from datetime import date
from types import SimpleNamespace

from src import db, issue
from src.analyse import Overview
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
    order = editor_order(rows, "model", Editor(lambda shown: [99, 0, 3, 3]))
    assert len([row for row in order if row[3] > -500]) == 1


def test_no_usable_answer_means_the_plain_scores_decide(monkeypatch, capsys):
    rows = [paper_row(number) for number in range(1, 13)]
    monkeypatch.setattr(issue, "checked_answer", lambda *args: None)
    assert editor_order(rows, "model", Editor(last_first)) == rows
    assert "plain scores" in capsys.readouterr().out


def test_no_key_means_the_plain_scores_decide():
    rows = [paper_row(number) for number in range(1, 13)]
    assert editor_order(rows, "model", None) == rows


def test_a_quiet_month_needs_no_editor():
    rows = [paper_row(number) for number in range(1, 8)]
    editor = Editor(last_first)
    assert editor_order(rows, "model", editor) == rows
    assert editor.calls == []


def test_an_opening_note_is_written_once_and_saved(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(issue, "have_key", lambda: True)
    monkeypatch.setattr(issue, "groq_client", lambda: None)
    answers = iter([Overview(overview="Rates matter — a lot.")])
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
