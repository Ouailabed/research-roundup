from datetime import date
from pathlib import Path
from types import SimpleNamespace

import feedparser
import pytest
from bs4 import BeautifulSoup

from src import collect, db
from src.collect import abstract_on_page, best_first_seen, cut_note, fill_from_pages, flip_name, is_research, new_paper, paper_from_entry, read_nber_listing, rebuild_abstract
from src.models import clean_abstract, clean_text, clean_url, make_id

SOURCE = {"name": "Sample", "group": "research_body"}
FEED = Path(__file__).parent / "sample_feed.xml"


def sample_papers():
    return [paper_from_entry(SOURCE, entry) for entry in feedparser.parse(FEED.read_bytes()).entries]


def test_saved_feed_gives_two_papers():
    assert len(sample_papers()) == 2


def test_nber_title_is_split_into_title_and_authors():
    paper = sample_papers()[0]
    assert paper.title == "A Made-Up Paper About Rates"
    assert paper.authors == "Ana Silva, Ben Okoye"


def test_nber_doi_comes_from_the_link():
    paper = sample_papers()[0]
    assert paper.doi == "10.3386/w99991"
    assert paper.id == "10.3386/w99991"


def test_abstract_is_cleaned():
    assert sample_papers()[0].abstract == "We study a made-up question. This abstract has odd spacing and a tag ."


def test_feed_date_is_read():
    first, second = sample_papers()
    assert first.published == ""
    assert second.published == "2026-10-12"


def test_tracking_is_dropped_from_urls():
    assert sample_papers()[1].url == "https://www.example.org/paper?id=7"
    assert clean_url("HTTPS://Example.org/a/#fromrss") == "https://example.org/a"


def test_same_url_gives_same_id():
    assert make_id("", "https://example.org/a?utm_source=x") == make_id("", "https://example.org/a#top")


def test_doi_wins_over_url_and_is_lower_case():
    assert make_id("10.1000/ABC", "https://example.org/a") == "10.1000/abc"


def test_clean_text_keeps_a_less_than_sign():
    assert clean_text("p < 0.05 and <i>more</i>") == "p < 0.05 and more"


def test_clean_text_removes_escaped_tags():
    assert clean_text("the first &lt;i&gt;real-time&lt;/i&gt; data") == "the first real-time data"


def test_clean_text_repairs_wrong_encoding():
    assert clean_text("Japanâ€™s markets") == "Japan’s markets"
    assert clean_text("GarcÃ\xada-Miralles") == "García-Miralles"


@pytest.mark.parametrize("text", [
    "Abstract We study rates.",
    "ABSTRACT: We study rates.",
    "We study rates. JEL Classification: E31, E52",
    "We study rates. (JEL E31, E52)",
])
def test_labels_and_jel_codes_leave_the_abstract(text):
    assert clean_abstract(text) == "We study rates."


def test_a_sentence_that_starts_with_summary_is_kept():
    assert clean_abstract("Summary statistics hide a lot.") == "Summary statistics hide a lot."


def test_a_placeholder_counts_as_no_abstract():
    assert clean_abstract("No abstract is available for this item.") == ""


@pytest.mark.parametrize("title", [
    "Front Matter",
    "Frontmatter of Econometrica 94 Iss. 2",
    "Backmatter of Econometrica Vol. 94 Iss. 5",
    "Recent Referees",
    "JPE Turnaround Times",
    "Report of Independent Auditor",
    "Comments and Discussion",
    "General Discussion",
    "Correction to: A Further Augmentation of the Solow Model",
    "Online Appendix for: How Do Voters Respond",
    "The Econometric Society 2025 Annual Report of the President",
])
def test_journal_housekeeping_is_not_research(title):
    assert not is_research(new_paper(SOURCE, title, "", "", "https://example.org/a", "", ""))


@pytest.mark.parametrize("title", [
    "Evidence from Annual Reports",
    "Comment on Asset Bubbles",
    "Nobel Lecture: Creative Destruction and Economic Growth",
])
def test_real_papers_are_kept(title):
    assert is_research(new_paper(SOURCE, title, "", "", "https://example.org/a", "", ""))


NBER_PAGE = """<html><body><div class="page-header__intro"><div class="page-header__intro-inner">
<p>We study a made-up question at length.</p><p>The full text is here.</p></div></div></body></html>"""


def test_nber_abstract_is_read_from_its_page():
    soup = BeautifulSoup(NBER_PAGE, "html.parser")
    assert abstract_on_page(soup) == "We study a made-up question at length. The full text is here."


def test_the_nber_listing_gets_full_abstracts_for_new_papers_only(monkeypatch):
    listing = {"results": [
        {"url": "/papers/w1", "title": "New paper", "authors": ["Ana Silva"], "abstract": "We study a made"},
        {"url": "/papers/w2", "title": "Known paper", "authors": ["Ben Okoye"], "abstract": "We also study"},
    ]}
    pages = []

    def fake_get(url, **kwargs):
        pages.append(url)
        return SimpleNamespace(json=lambda: listing if not pages[1:] else {"results": []}, text=NBER_PAGE)

    monkeypatch.setattr(collect, "polite_get", fake_get)
    known = {"https://www.nber.org/papers/w2"}
    dates = {"10.3386/w1": "2026-09-14", "10.3386/w2": "2026-09-15"}
    new, old = read_nber_listing(SOURCE, dates, known)
    assert new.abstract == "We study a made-up question at length. The full text is here."
    assert old.abstract == "We also study"
    assert "https://www.nber.org/papers/w2" not in pages


def test_a_page_that_fails_keeps_the_short_abstract(monkeypatch):
    def broken_get(url, **kwargs):
        raise RuntimeError("www.nber.org answered 500")

    monkeypatch.setattr(collect, "polite_get", broken_get)
    paper = new_paper(SOURCE, "A paper", "", "We study a made", "https://www.nber.org/papers/w1", "", "")
    fill_from_pages({"name": "NBER", "abstract_from_page": True}, [paper], set())
    assert paper.abstract == "We study a made"


def test_abstracts_that_stop_mid_sentence_raise_a_warning():
    assert "3 of 5 abstracts" in cut_note(["We study", "We find", "We also", "All done.", "Is it? Yes."])


def test_full_abstracts_raise_no_warning():
    assert cut_note(["We study rates.", "Do rates matter?", "It ends (see above)"]) == ""
    assert cut_note([]) == ""


def test_a_long_abstract_with_no_full_stop_is_not_called_cut():
    assert cut_note(["We study rates " * 40]) == ""


def test_collecting_comes_due_after_a_week(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    conn = db.connect()
    row = {"run_at": "2026-11-01T02:00:00+00:00", "source": "NBER", "source_group": "x", "route": "rss", "status": "working", "found": 1, "new": 0, "missing_abstracts": 0, "note": ""}
    db.save_health(conn, [row])
    conn.close()
    assert not collect.collect_is_due(date(2026, 11, 7))
    assert collect.collect_is_due(date(2026, 11, 8))


def test_a_database_with_no_runs_does_not_collect_by_itself(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    assert not collect.collect_is_due(date(2026, 11, 8))


def test_a_missing_abstract_is_filled_from_repec(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    page = '<html><head><meta name="citation_abstract" content="Abstract We study rates."></head></html>'
    asked = []

    def fake_get(url, **kwargs):
        asked.append(url)
        return SimpleNamespace(text=page)

    monkeypatch.setattr(collect, "polite_get", fake_get)
    conn = db.connect()
    db.save_papers(conn, [new_paper({"name": "JPE", "group": "journal"}, "A paper", "", "", "https://doi.org/10.1086/742714", "10.1086/742714", "")])
    collect.fill_from_repec(conn, {"name": "JPE", "repec_journal": "ucp/jpolec"})
    assert asked == ["https://ideas.repec.org/a/ucp/jpolec/doi10.1086-742714.html"]
    assert conn.execute("SELECT abstract FROM papers").fetchone()[0] == "We study rates."
    conn.close()


def test_a_paper_repec_does_not_list_yet_stays_empty(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")

    def not_found(url, **kwargs):
        raise RuntimeError("ideas.repec.org answered 404")

    monkeypatch.setattr(collect, "polite_get", not_found)
    conn = db.connect()
    db.save_papers(conn, [new_paper({"name": "JPE", "group": "journal"}, "A paper", "", "", "https://doi.org/10.1086/1", "10.1086/1", "")])
    collect.fill_from_repec(conn, {"name": "JPE", "repec_journal": "ucp/jpolec"})
    assert conn.execute("SELECT abstract FROM papers").fetchone()[0] == ""
    conn.close()


def test_openalex_abstract_is_rebuilt_in_order():
    assert rebuild_abstract({"study": [1], "We": [0], "rates": [2]}) == "We study rates"
    assert rebuild_abstract(None) == ""


def test_names_are_flipped():
    assert flip_name("Silva, Ana") == "Ana Silva"
    assert flip_name("Ana Silva") == "Ana Silva"


def test_best_first_seen_never_guesses_a_month():
    today = "2026-10-31"
    assert best_first_seen("2026-09-14", "x", today) == "2026-09-14"
    assert best_first_seen("2026-09", "x", today) == "2026-09-01"
    assert best_first_seen("2026", "x", today) == "2026-01-01"
    assert best_first_seen("", "2026-10-30", today) == "2026-10-30"


def test_first_seen_is_never_in_the_future():
    assert best_first_seen("2026-12-01", "x", "2026-10-31") == "2026-10-31"
