from src.publish import clean_topics


def test_capitals_and_spaces_make_no_new_topic():
    assert clean_topics(["Inflation", " inflation "]) == ["inflation"]


def test_us_and_uk_spelling_are_one_topic():
    assert clean_topics(["labor markets", "labour markets"]) == ["labour markets"]


def test_near_names_are_one_topic():
    assert clean_topics(["Labor market", "artificial intelligence", "AI"]) == ["ai", "labour markets"]


def test_a_word_that_only_contains_labor_is_left_alone():
    assert clean_topics(["laboratory experiments"]) == ["laboratory experiments"]
