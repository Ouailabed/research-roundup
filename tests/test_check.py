import json

import pytest

from src.analyse import ADVANCED_NOTE, Score, analyse_paper
from src.check import named_places, tag_conflict, unseen_numbers
from tests.test_analyse import FakeClient, GOOD

PAPER = {"id": "x", "title": "Superbonus in Italy", "authors": "A. Author", "source": "Banca d'Italia", "abstract": "We study Italian builders."}


@pytest.mark.parametrize("text, tag", [
    ("The Superbonus in Italy", "EM"),
    ("Evidence from Spain and the US", "EM"),
    ("Doctors in Chile", "DM"),
])
def test_a_tag_that_cannot_fit_is_flagged(text, tag):
    assert tag_conflict(tag, text)


@pytest.mark.parametrize("text, tag", [
    ("The Superbonus in Italy", "DM"),
    ("Doctors in Chile", "EM"),
    ("Trade between China and Germany", "DM"),
    ("Trade between China and Germany", "EM"),
    ("A theory of money", "DM"),
    ("A theory of money", "EM"),
    ("Italy and Spain", "Transversal"),
])
def test_a_tag_that_can_fit_is_left_alone(text, tag):
    assert tag_conflict(tag, text) == ""


def test_bulgaria_counts_as_advanced_since_it_joined_the_euro():
    assert named_places("Firms in Bulgaria")[0] == {"Bulgaria"}


def test_latin_american_is_not_american():
    assert named_places("Latin American firms") == (set(), {"Latin American"})


def test_us_in_capitals_is_a_country_but_us_in_lower_case_is_not():
    assert named_places("Tariffs in the US")[0] == {"US"}
    assert named_places("Tell us about tariffs")[0] == set()


def test_a_number_the_source_gives_is_fine():
    assert unseen_numbers("It rose by 3.5 percent.", "Prices rose by 3.5 percent.") == []


def test_a_number_the_source_lacks_is_flagged():
    assert unseen_numbers("It rose by 4 percent.", "Prices rose.") == ["4"]


def test_a_clashing_tag_gets_a_second_look():
    client = FakeClient(json.dumps(GOOD), json.dumps({**GOOD, "market_focus": "DM", "tag_reason": "names Italy"}))
    assert analyse_paper(client, "model", PAPER, Score).market_focus == "DM"
    assert client.calls == 2


def test_the_second_look_stands_even_if_it_keeps_the_tag():
    client = FakeClient(json.dumps(GOOD), json.dumps(GOOD))
    assert analyse_paper(client, "model", PAPER, Score).market_focus == "EM"
    assert client.calls == 2


def test_a_failed_second_look_keeps_the_first_answer():
    client = FakeClient(json.dumps(GOOD), "not json", "not json")
    assert analyse_paper(client, "model", PAPER, Score).market_focus == "EM"


def test_a_tag_with_no_clash_gets_no_second_look():
    client = FakeClient(json.dumps({**GOOD, "market_focus": "DM"}))
    analyse_paper(client, "model", PAPER, Score)
    assert client.calls == 1


def test_the_prompt_and_the_check_use_the_same_list():
    # Each name in the prompt's list must be one the check can recognise.
    for name in ADVANCED_NOTE:
        assert named_places(name)[0], name
