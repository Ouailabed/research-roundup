import json
from types import SimpleNamespace

import pytest

from src import db, factcheck, issue
from src.analyse import Analysis, Check, DailyLimitReached
from src.factcheck import CheckerUnavailable, check_writeup
from tests.test_analyse import groq_outage, groq_refusal
from tests.test_db import RESULT, make_paper

PAPER = {"title": "Trade and inflation", "abstract": "Less trade reduces the sacrifice ratio by almost one-half."}
WRITEUP = {"summary": "Less trade raises the sacrifice ratio.", "takeaways": ["One.", "Two.", "Three."], "why_it_matters": "Rates."}
RIGHT = "Less trade reduces the sacrifice ratio by almost one-half."


def problem(field="summary", kind="backwards"):
    return {"field": field, "kind": kind, "write_up_says": "raises", "abstract_says": "reduces"}


def check(*problems, summary=RIGHT, takeaways=("One.", "Two.", "Three."), why="Rates."):
    return Check(problems=list(problems), summary=summary, takeaways=list(takeaways), why_it_matters=why)


def asker(*answers):
    replies = iter(answers)

    def ask(model, text):
        ask.seen.append(text)
        return next(replies)

    ask.seen = []
    return ask


def test_a_clean_write_up_is_left_exactly_as_it_was():
    kept, status, problems = check_writeup(PAPER, WRITEUP, "checker", asker(check(summary="Something else entirely.")))
    assert (kept, status, problems) == (WRITEUP, "clean", [])


def test_a_reversed_claim_is_corrected_and_the_correction_is_checked_again():
    ask = asker(check(problem()), check())
    kept, status, problems = check_writeup(PAPER, WRITEUP, "checker", ask)
    assert status == "corrected"
    assert kept["summary"] == RIGHT
    assert len(ask.seen) == 2 and RIGHT in ask.seen[1]
    assert problems[0]["kind"] == "backwards"


def test_only_the_fields_with_a_problem_are_changed():
    answer = check(problem("takeaway 2", "invented"), summary="A rewrite nobody asked for.", takeaways=("One.", "Fixed two.", "Three."))
    kept, status, _ = check_writeup(PAPER, WRITEUP, "checker", asker(answer, check()))
    assert kept["summary"] == WRITEUP["summary"]
    assert kept["takeaways"] == ["One.", "Fixed two.", "Three."]
    assert status == "corrected"


def test_a_correction_that_still_fails_is_marked_unresolved_and_put_back():
    kept, status, problems = check_writeup(PAPER, WRITEUP, "checker", asker(check(problem()), check(problem("summary", "invented"))))
    assert status == "unresolved"
    assert kept["summary"] == WRITEUP["summary"]
    assert [one["kind"] for one in problems] == ["backwards", "invented"]


def test_a_rewrite_that_adds_an_error_goes_back_but_a_confirmed_fix_stays():
    first = check(problem("summary"), problem("takeaway 2", "loose"), takeaways=("One.", "Two, with an invented cause.", "Three."))
    second = check(problem("takeaway 2", "invented"))
    kept, status, _ = check_writeup(PAPER, WRITEUP, "checker", asker(first, second))
    assert status == "unresolved"
    assert kept["summary"] == RIGHT
    assert kept["takeaways"][1] == "Two."


def test_a_loose_word_left_after_a_correction_is_recorded_but_not_held_against_it():
    _, status, problems = check_writeup(PAPER, WRITEUP, "checker", asker(check(problem()), check(problem("summary", "loose"))))
    assert status == "corrected"
    assert [one["kind"] for one in problems] == ["backwards", "loose"]


def test_no_answer_on_the_second_look_means_the_correction_is_not_trusted():
    kept, status, _ = check_writeup(PAPER, WRITEUP, "checker", asker(check(problem()), None))
    assert (kept, status) == (WRITEUP, "unresolved")


def test_no_answer_changes_nothing():
    kept, status, _ = check_writeup(PAPER, WRITEUP, "checker", asker(None))
    assert (kept, status) == (WRITEUP, "no answer")


def test_a_correction_never_brings_in_an_em_dash():
    answer = check(problem(), summary="Less trade " + chr(0x2014) + " reduces it.")
    kept, _, _ = check_writeup(PAPER, WRITEUP, "checker", asker(answer, check()))
    assert chr(0x2014) not in kept["summary"]


def test_the_answer_shape_meets_strict_mode():
    schema = Check.model_json_schema()

    def walk(node):
        if "$ref" in node:
            walk(schema["$defs"][node["$ref"].split("/")[-1]])
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert sorted(node["required"]) == sorted(node["properties"])
            for child in node["properties"].values():
                walk(child)
        if node.get("type") == "array":
            walk(node["items"])

    walk(schema)


def test_a_groq_error_makes_the_checker_unavailable(monkeypatch):
    monkeypatch.setattr(factcheck, "groq_client", lambda: "client")
    def broken(*args):
        raise groq_refusal("model not found")

    monkeypatch.setattr(factcheck, "checked_answer", broken)
    with pytest.raises(CheckerUnavailable):
        factcheck.ask_checker("gone/model", "text")


def test_a_long_outage_makes_the_checker_unavailable(monkeypatch):
    monkeypatch.setattr(factcheck, "groq_client", lambda: "client")
    def outage(*args):
        raise groq_outage()

    monkeypatch.setattr(factcheck, "checked_answer", outage)
    with pytest.raises(CheckerUnavailable):
        factcheck.ask_checker("model", "text")


def test_the_daily_limit_is_passed_on_so_the_issue_waits(monkeypatch):
    monkeypatch.setattr(factcheck, "groq_client", lambda: "client")
    def limit(*args):
        raise DailyLimitReached("the model has used up today's allowance")

    monkeypatch.setattr(factcheck, "checked_answer", limit)
    with pytest.raises(DailyLimitReached):
        factcheck.ask_checker("model", "text")


def test_the_checker_asks_for_the_check_shape(monkeypatch):
    asked = []
    monkeypatch.setattr(factcheck, "groq_client", lambda: "client")
    monkeypatch.setattr(factcheck, "checked_answer", lambda client, model, rules, text, shape, name: asked.append((client, model, shape)))
    factcheck.ask_checker("qwen/qwen3.8-27b", "text")
    assert asked == [("client", "qwen/qwen3.8-27b", Check)]


@pytest.fixture
def written_issue(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    conn = db.connect()
    papers = [make_paper(f"p{number}", source=f"Source {number}") for number in range(3)]
    db.save_papers(conn, papers)
    for paper in papers:
        db.save_analysis(conn, paper.id, "cheap", RESULT)
        db.save_writeup(conn, paper.id, "strong", Analysis(
            summary="Less trade raises the sacrifice ratio.", market_focus="DM", tag_reason="names Japan",
            relevance=9, topics=["rates"], takeaways=["a", "b", "c"], why_it_matters="It matters."))
    db.save_issue(conn, "2026-10", [paper.id for paper in papers])
    yield conn
    conn.close()


def test_without_a_key_the_issue_goes_out_unchecked(written_issue, monkeypatch, capsys):
    monkeypatch.setattr(issue, "have_key", lambda: False)
    assert issue.fact_check(written_issue, "2026-10", "openai/gpt-oss-120b") is None
    assert "not fact-checked" in capsys.readouterr().out
    assert db.check_status(written_issue, "p0") is None


def test_corrections_are_saved_and_labelled_and_a_checked_paper_is_not_checked_again(written_issue, monkeypatch):
    monkeypatch.setattr(issue, "have_key", lambda: True)
    calls = []

    def fake(paper, writeup, model):
        calls.append(paper["id"])
        if paper["id"] == "p1":
            return {**writeup, "summary": RIGHT}, "corrected", [problem()]
        return writeup, "clean", []

    monkeypatch.setattr(issue, "check_writeup", fake)
    assert issue.fact_check(written_issue, "2026-10", "openai/gpt-oss-120b") == "openai/gpt-oss-120b"
    fixed = db.writeup_of(written_issue, "p1")
    assert fixed["summary"] == RIGHT
    assert fixed["model"] == "strong (corrected by openai/gpt-oss-120b against the abstract)"
    assert db.writeup_of(written_issue, "p0")["model"] == "strong"
    assert issue.fact_check(written_issue, "2026-10", "openai/gpt-oss-120b") == "openai/gpt-oss-120b"
    assert calls == ["p0", "p1", "p2"]


def test_an_unresolved_check_means_the_newsletter_claims_no_check(written_issue, monkeypatch, capsys):
    monkeypatch.setattr(issue, "have_key", lambda: True)
    monkeypatch.setattr(issue, "check_writeup", lambda paper, writeup, model: (writeup, "unresolved" if paper["id"] == "p2" else "clean", []))
    assert issue.fact_check(written_issue, "2026-10", "openai/gpt-oss-120b") is None
    # Nothing was kept from the checker, so the write-up and its label are as the writer left them.
    assert db.writeup_of(written_issue, "p2")["model"] == "strong"
    assert "Read it before this issue goes out" in capsys.readouterr().out


def test_a_partly_corrected_write_up_says_so(written_issue, monkeypatch):
    monkeypatch.setattr(issue, "have_key", lambda: True)
    monkeypatch.setattr(issue, "check_writeup", lambda paper, writeup, model: ({**writeup, "summary": RIGHT}, "unresolved", []))
    issue.fact_check(written_issue, "2026-10", "openai/gpt-oss-120b")
    assert db.writeup_of(written_issue, "p0")["model"] == "strong (partly corrected by openai/gpt-oss-120b, the rest not confirmed)"


def test_a_correction_means_the_opening_note_is_written_again(written_issue, monkeypatch):
    monkeypatch.setattr(issue, "have_key", lambda: True)
    db.save_overview(written_issue, "2026-10", "strong", "Less trade raises the sacrifice ratio.")
    monkeypatch.setattr(issue, "check_writeup", lambda paper, writeup, model: ({**writeup, "summary": RIGHT}, "corrected", []))
    issue.fact_check(written_issue, "2026-10", "openai/gpt-oss-120b")
    assert db.saved_overview(written_issue, "2026-10") == ""


def test_a_clean_issue_keeps_its_opening_note(written_issue, monkeypatch):
    monkeypatch.setattr(issue, "have_key", lambda: True)
    db.save_overview(written_issue, "2026-10", "strong", "A note.")
    monkeypatch.setattr(issue, "check_writeup", lambda paper, writeup, model: (writeup, "clean", []))
    issue.fact_check(written_issue, "2026-10", "openai/gpt-oss-120b")
    assert db.saved_overview(written_issue, "2026-10") == "A note."


def test_write_ups_audited_by_hand_are_never_rewritten(written_issue, monkeypatch):
    monkeypatch.setattr(issue, "have_key", lambda: True)
    for paper_id in ("p0", "p1", "p2"):
        db.save_check(written_issue, paper_id, "Claude and Codex", "audited", [])
    monkeypatch.setattr(issue, "check_writeup", lambda *args: pytest.fail("an audited write-up was sent to the checker"))
    # They were audited, not checked by this step, so the newsletter doesn't claim this step checked them.
    assert issue.fact_check(written_issue, "2026-10", "openai/gpt-oss-120b") is None


def test_a_checker_that_stops_working_leaves_the_rest_unchecked(written_issue, monkeypatch, capsys):
    monkeypatch.setattr(issue, "have_key", lambda: True)

    def broken(paper, writeup, model):
        raise CheckerUnavailable("NotFoundError 404")

    monkeypatch.setattr(issue, "check_writeup", broken)
    assert issue.fact_check(written_issue, "2026-10", "openai/gpt-oss-120b") is None
    assert "goes out unchecked" in capsys.readouterr().out


def test_no_answer_is_tried_again_next_time(written_issue, monkeypatch):
    monkeypatch.setattr(issue, "have_key", lambda: True)
    monkeypatch.setattr(issue, "check_writeup", lambda paper, writeup, model: (writeup, "no answer", []))
    issue.fact_check(written_issue, "2026-10", "openai/gpt-oss-120b")
    calls = []
    monkeypatch.setattr(issue, "check_writeup", lambda paper, writeup, model: (calls.append(paper["id"]), (writeup, "clean", []))[1])
    assert issue.fact_check(written_issue, "2026-10", "openai/gpt-oss-120b") == "openai/gpt-oss-120b"
    assert calls == ["p0", "p1", "p2"]


def test_the_newsletter_says_it_was_checked_only_when_it_was():
    paper = {"market_focus": "DM", "url": "https://example.org", "title": "T", "authors": "A", "source": "S", "published_label": "",
             "summary": "S.", "takeaways": ["a", "b", "c"], "why_it_matters": "W.", "tag_reason": "R."}
    assert "compared each write-up with its abstract" in issue.render_issue("2026-10", [paper], 10, 5, "", "qwen/qwen3.8-27b")
    assert "compared each write-up" not in issue.render_issue("2026-10", [paper], 10, 5, "")


def test_the_measure_stops_at_the_daily_limit(capsys):
    def limit(model, text):
        raise DailyLimitReached("the model has used up today's allowance")

    assert factcheck.measure("checker", limit) == {"serious": [0, 0], "loose": [0, 0], "clean": [0, 0]}
    assert "Stopped" in capsys.readouterr().out


def test_the_measure_uses_the_16_audited_write_ups():
    audited = json.loads(factcheck.AUDITED.read_text(encoding="utf-8"))
    assert [sum(row["audit"] == kind for row in audited) for kind in ("serious", "loose", "clean")] == [8, 3, 5]
    tally = factcheck.measure("checker", lambda model, text: check(problem()))
    assert tally == {"serious": [8, 8], "loose": [3, 3], "clean": [5, 5]}
