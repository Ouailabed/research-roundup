import pytest


@pytest.fixture(autouse=True)
def no_real_checker(monkeypatch):
    # A key set on this computer must never make a test call the real checker and spend money.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
