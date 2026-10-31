import json
from types import SimpleNamespace

import httpx
import pytest
from groq import BadRequestError
from pydantic import ValidationError

from src.analyse import Analysis, Score, analyse_paper, paper_text

PAPER = {"id": "x", "title": "A Title", "authors": "A. Author", "source": "NBER", "abstract": "An abstract."}
GOOD = {
    "summary": "One sentence. Two sentences.",
    "market_focus": "EM",
    "tag_reason": "names Brazil",
    "relevance": 7,
    "topics": ["inflation"],
}


class FakeClient:
    """Stands in for Groq and hands back the answers it was given, one per call."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = 0
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        self.calls += 1
        message = SimpleNamespace(content=self.answers.pop(0))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_valid_answer_is_accepted():
    result = analyse_paper(FakeClient(json.dumps(GOOD)), "model", PAPER, Score)
    assert result.market_focus == "EM"


def test_wrong_tag_is_refused():
    with pytest.raises(ValidationError):
        Score.model_validate({**GOOD, "market_focus": "Global"})


def test_score_must_be_1_to_10():
    with pytest.raises(ValidationError):
        Score.model_validate({**GOOD, "relevance": 11})


def test_extra_fields_are_refused():
    with pytest.raises(ValidationError):
        Score.model_validate({**GOOD, "invented": "x"})


def test_full_analysis_needs_three_takeaways():
    full = {**GOOD, "why_it_matters": "It matters.", "takeaways": ["one", "two"]}
    with pytest.raises(ValidationError):
        Analysis.model_validate(full)
    assert Analysis.model_validate({**full, "takeaways": ["one", "two", "three"]})


def test_bad_answer_is_retried_once():
    client = FakeClient("not json", json.dumps(GOOD))
    assert analyse_paper(client, "model", PAPER, Score).relevance == 7
    assert client.calls == 2


def test_two_bad_answers_give_none():
    client = FakeClient("not json", json.dumps({**GOOD, "relevance": 0}))
    assert analyse_paper(client, "model", PAPER, Score) is None
    assert client.calls == 2


def groq_refusal(message):
    response = httpx.Response(400, request=httpx.Request("POST", "https://example.org"))
    return BadRequestError(message, response=response, body=None)


class RefusingClient(FakeClient):
    def create(self, **kwargs):
        self.calls += 1
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        message = SimpleNamespace(content=answer)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def test_a_refused_answer_is_retried_and_the_run_carries_on():
    client = RefusingClient(groq_refusal("json_validate_failed"), json.dumps(GOOD))
    assert analyse_paper(client, "model", PAPER, Score).relevance == 7


def test_two_refused_answers_give_none():
    client = RefusingClient(groq_refusal("json_validate_failed"), groq_refusal("json_validate_failed"))
    assert analyse_paper(client, "model", PAPER, Score) is None


def test_any_other_bad_request_stops():
    with pytest.raises(BadRequestError):
        analyse_paper(RefusingClient(groq_refusal("model not found")), "model", PAPER, Score)


def test_prompt_text_uses_only_the_paper():
    text = paper_text(PAPER)
    assert "A Title" in text and "An abstract." in text
