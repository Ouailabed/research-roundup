from src.dedupe import find_duplicates, normalise, same_title


def test_same_title_ignores_case_and_punctuation():
    first = normalise("Tariffs and Inflation: Evidence from Firms")
    second = normalise("Tariffs and inflation, evidence from firms!")
    assert same_title(first, second)


def test_different_titles_do_not_match():
    first = normalise("Tariffs and Inflation: Evidence from Firms")
    second = normalise("Banks and Inflation: Evidence from Households")
    assert not same_title(first, second)


def test_longest_abstract_is_kept():
    rows = [
        ("short", "Tariffs and Inflation: Evidence from Firms", "Bank A", 400),
        ("long", "Tariffs and inflation: evidence from firms", "Bank B", 900),
    ]
    assert find_duplicates(rows) == {"short": "long"}


def test_same_source_is_never_merged():
    rows = [
        ("one", "Comments and Discussion on Monetary Policy", "BPEA", 300),
        ("two", "Comments and Discussion on Monetary Policy", "BPEA", 300),
    ]
    assert find_duplicates(rows) == {}


def test_papers_with_no_abstract_are_left_alone():
    rows = [
        ("one", "Tariffs and Inflation: Evidence from Firms", "Bank A", 0),
        ("two", "Tariffs and Inflation: Evidence from Firms", "Bank B", 800),
    ]
    assert find_duplicates(rows) == {}


def test_three_copies_all_point_to_one_paper():
    rows = [
        ("a", "Tariffs and Inflation: Evidence from Firms", "Bank A", 900),
        ("b", "Tariffs and Inflation: Evidence from Firms", "Bank B", 500),
        ("c", "Tariffs and Inflation: Evidence from Firms", "Bank C", 400),
    ]
    assert find_duplicates(rows) == {"b": "a", "c": "a"}
