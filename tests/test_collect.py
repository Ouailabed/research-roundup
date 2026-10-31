from pathlib import Path

import feedparser

from src.collect import best_first_seen, flip_name, paper_from_entry, rebuild_abstract
from src.models import clean_text, clean_url, make_id

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
