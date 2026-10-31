from datetime import date

from src.issue import choose_papers, date_label, last_full_month, no_em_dash

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


def test_last_full_month():
    assert last_full_month(date(2026, 11, 1)) == "2026-10"
    assert last_full_month(date(2026, 1, 15)) == "2025-12"


def test_date_labels():
    assert date_label("2026-10-03") == "3 October 2026"
    assert date_label("2026-10") == "October 2026"
    assert date_label("2026") == "2026"


def test_em_dashes_are_removed():
    assert no_em_dash("Rates — and more") == "Rates, and more"
