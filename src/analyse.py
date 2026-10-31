import json
import time
from typing import Literal

from groq import BadRequestError, RateLimitError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.ai import groq_client, have_key, load_settings
from src.db import connect, papers_to_analyse, save_analysis

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


LONGEST_ANSWER = {Score: 800, Analysis: 2000}


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
    return float(error.response.headers.get("retry-after", 60))


def model_options(model, shape):
    # These models think before they answer, and that counts towards the limit. Scoring doesn't need much of it.
    if shape is Score and model.startswith("openai/gpt-oss"):
        return {"reasoning_effort": "low"}
    return {}


def call_model(client, model, paper, shape):
    while True:
        try:
            reply = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": RULES}, {"role": "user", "content": paper_text(paper)}],
                response_format=response_format(shape),
                max_completion_tokens=LONGEST_ANSWER[shape],
                **model_options(model, shape),
            )
            return reply.choices[0].message.content
        except RateLimitError as error:
            if "per day" in str(error):
                raise DailyLimitReached(f"{model} has used up today's allowance") from error
            time.sleep(seconds_to_wait(error))


def analyse_paper(client, model, paper, shape):
    """Returns a checked result, or None if the answer is still invalid after one retry."""
    for attempt in (1, 2):
        try:
            return shape.model_validate(json.loads(call_model(client, model, paper, shape)))
        except BadRequestError as error:
            # Groq refuses an answer that breaks the JSON shape. Any other 400 is a real fault.
            if "json_validate_failed" not in str(error):
                raise
            print(f"Groq refused the answer for {paper['id']}, attempt {attempt}")
        except (json.JSONDecodeError, ValidationError) as error:
            print(f"Invalid answer for {paper['id']}, attempt {attempt}: {str(error)[:120]}")
    return None


def analyse_all(limit=None):
    if not have_key():
        print("No GROQ_API_KEY found, so no new analysis. Saved results still work.")
        return
    settings = load_settings()
    models = list(settings["models"]["cheap"])
    conn = connect()
    client = groq_client()
    papers = papers_to_analyse(conn, settings["analyse_from"])[:limit]
    print(f"{len(papers)} papers to analyse")
    done = 0
    for paper in papers:
        result = None
        while models:
            try:
                result = analyse_paper(client, models[0], paper, Score)
                break
            except DailyLimitReached as error:
                print(f"{error}, so the next model takes over.")
                models.pop(0)
        if not models:
            print("Every scoring model has used up today's allowance. Run this again later and it carries on.")
            break
        if result:
            save_analysis(conn, paper["id"], models[0], result)
            done += 1
            if done % 25 == 0:
                print(f"{done} done", flush=True)
    print(f"Analysed {done} papers")
    conn.close()


if __name__ == "__main__":
    analyse_all(5)
