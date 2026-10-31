import os

import yaml
from dotenv import load_dotenv
from groq import Groq

from src.config import ROOT

load_dotenv()


def load_settings():
    with open(ROOT / "config" / "settings.yaml", encoding="utf-8") as file:
        return yaml.safe_load(file)


def have_key():
    return bool(os.getenv("GROQ_API_KEY"))


def groq_client():
    # max_retries=0 means our own code decides when to wait and try again.
    return Groq(api_key=os.getenv("GROQ_API_KEY"), max_retries=0)


if __name__ == "__main__":
    reply = groq_client().chat.completions.create(
        model=load_settings()["models"]["cheap"],
        messages=[{"role": "user", "content": "Reply with one word: ready"}],
    )
    print(reply.choices[0].message.content)
