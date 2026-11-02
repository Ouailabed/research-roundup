import pytest

from src import factcheck


@pytest.fixture(autouse=True)
def no_real_checker(monkeypatch):
    # A test must never reach the real checker, even on a computer with a Groq key set.
    def refuse():
        pytest.fail("a test tried to call Groq for the fact-check")

    monkeypatch.setattr(factcheck, "groq_client", refuse)
