import json
import time
from typing import Literal

from groq import RateLimitError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.ai import groq_client, have_key, load_settings
from src.db import connect, papers_to_analyse, save_analysis

LONGEST_WAIT = 120
LONGEST_ABSTRACT = 2500

RULES = """You help a markets research team at an investment bank find useful economics papers.

Use only the title, abstract and metadata you are given. Never add findings, numbers, names or places that are not there. If the abstract does not say something, leave it out.

Choose market_focus with these rules. Advanced economies are the ones on the IMF's advanced economies list, for example the United States, the euro area, the United Kingdom, Japan, Canada, Australia, Switzerland, Sweden and Norway. Every other country counts as emerging.
- DM: mainly about advanced economies.
- EM: mainly about emerging or developing economies.
- Transversal: global, many regions, or theory and methods not tied to one group. If the abstract names no country or region, use Transversal.

tag_reason is one line that points to words in the abstract.

relevance is a whole number from 1 to 10. Use 9 or 10 for a clear use in views on rates, currencies, credit, inflation, growth or central bank policy. Use 5 for useful background. Use 1 for no link to markets or the economy.

topics are 1 to 3 short subject labels, such as inflation, labour markets or banking.

Write in plain English and never use em dashes."""


class Score(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(description="Two plain sentences on what the paper asks and finds.")
    market_focus: Literal["EM", "DM", "Transversal"]
    tag_reason: str
    relevance: int = Field(ge=1, le=10)
    topics: list[str] = Field(min_length=1, max_length=3)


class Analysis(Score):
    summary: str = Field(description="Three or four plain sentences on the question, the method and the finding.")
    takeaways: list[str] = Field(min_length=3, max_length=3, description="Three key takeaways.")
    why_it_matters: str = Field(description="Why this matters for a markets research team.")


class DailyLimitReached(Exception):
    pass


def response_format(shape):
    return {
        "type": "json_schema",
        "json_schema": {"name": shape.__name__.lower(), "strict": True, "schema": shape.model_json_schema()},
    }


def paper_text(paper):
    return "\n".join([
        f"Title: {paper['title']}",
        f"Authors: {paper['authors']}",
        f"Source: {paper['source']}",
        f"Abstract: {paper['abstract'][:LONGEST_ABSTRACT]}",
    ])


def seconds_to_wait(error):
    return float(error.response.headers.get("retry-after", LONGEST_WAIT))


def call_model(client, model, paper, shape):
    while True:
        try:
            reply = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": RULES}, {"role": "user", "content": paper_text(paper)}],
                response_format=response_format(shape),
            )
            return reply.choices[0].message.content
        except RateLimitError as error:
            wait = seconds_to_wait(error)
            # A short wait is the per-minute limit. A long one means today's allowance has run out.
            if wait > LONGEST_WAIT:
                raise DailyLimitReached(f"Groq asked us to wait {wait:.0f} seconds") from error
            time.sleep(wait)


def analyse_paper(client, model, paper, shape):
    """Returns a checked result, or None if the answer is still invalid after one retry."""
    for attempt in (1, 2):
        text = call_model(client, model, paper, shape)
        try:
            return shape.model_validate(json.loads(text))
        except (json.JSONDecodeError, ValidationError) as error:
            print(f"Invalid answer for {paper['id']}, attempt {attempt}: {str(error)[:120]}")
    return None


def analyse_all(limit=None):
    if not have_key():
        print("No GROQ_API_KEY found, so no new analysis. Saved results still work.")
        return
    settings = load_settings()
    model = settings["models"]["cheap"]
    conn = connect()
    client = groq_client()
    papers = papers_to_analyse(conn, model, settings["analyse_from"])[:limit]
    print(f"{len(papers)} papers to analyse with {model}")
    done = 0
    for paper in papers:
        try:
            result = analyse_paper(client, model, paper, Score)
        except DailyLimitReached as error:
            print(f"Stopped for today: {error}. Run this again later and it carries on.")
            break
        if result:
            save_analysis(conn, paper["id"], model, result)
            done += 1
            if done % 25 == 0:
                print(f"{done} done")
    print(f"Analysed {done} papers")
    conn.close()


if __name__ == "__main__":
    analyse_all(5)
