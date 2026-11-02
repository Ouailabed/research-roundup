import json
import time
from typing import Literal

from groq import APIConnectionError, BadRequestError, InternalServerError, RateLimitError
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.ai import groq_client, have_key, load_settings
from src.check import tag_conflict
from src.db import connect, papers_to_analyse, save_analysis, save_failure

LONGEST_ABSTRACT = 2500
MOST_OUTAGES = 3
SECONDS_AFTER_OUTAGE = 30
# Table B of the IMF's World Economic Outlook, April 2026. It changes: Bulgaria joined when it took the euro.
ADVANCED_NOTE = (
    "Andorra", "Australia", "Austria", "Belgium", "Bulgaria", "Canada", "Croatia", "Cyprus", "the Czech Republic", "Denmark", "Estonia",
    "Finland", "France", "Germany", "Greece", "Hong Kong", "Iceland", "Ireland", "Israel", "Italy", "Japan", "Korea", "Latvia",
    "Liechtenstein", "Lithuania", "Luxembourg", "Macao", "Malta", "the Netherlands", "New Zealand", "Norway", "Portugal", "Puerto Rico",
    "San Marino", "Singapore", "the Slovak Republic", "Slovenia", "Spain", "Sweden", "Switzerland", "Taiwan", "the United Kingdom",
    "the United States",
)

RULES = f"""You help a markets research team at an investment bank find useful economics papers.

Use only the title, abstract and metadata you are given. Never add findings, numbers, names or places that are not there. If the abstract does not say something, leave it out.

Keep every effect in the direction the abstract gives it, and keep words like "at least" or "almost". If the abstract only says a paper has implications for something, say that and no more. Never add a policy conclusion of your own.

Choose market_focus with these rules. Advanced economies are exactly the ones on the IMF's list of April 2026: {", ".join(ADVANCED_NOTE)}. The euro area counts as advanced. Every other country counts as emerging, including Chile, China, Hungary, Mexico, Poland and Romania.
- DM: mainly about advanced economies.
- EM: mainly about emerging or developing economies.
- Transversal: global, many regions, or theory and methods not tied to one group. If the abstract names no country or region, use Transversal.

A national programme, dataset or institution names its country, for example Medicare, SIPP or the FOMC. The paper's publisher does not: a Federal Reserve working paper isn't about the United States unless its abstract says so.

tag_reason is one short sentence saying why the tag fits. It must name the country, region or method in the abstract that decided it, for example "The paper studies firms in India, an emerging economy."

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


class Ranking(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ranking: list[int] = Field(min_length=1, description="Paper numbers, best first.")


class Overview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overview: str = Field(description="Two or three plain sentences.")


LONGEST_ANSWER = {Score: 800, Analysis: 2000, Ranking: 2500, Overview: 1000}
# These models think before they answer, and that counts towards the limit. Scoring doesn't need much of it.
THINKING = {Score: "low", Ranking: "medium"}


class DailyLimitReached(Exception):
    def __init__(self, message, seconds=60):
        super().__init__(message)
        self.seconds = seconds


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
    if shape in THINKING and model.startswith("openai/gpt-oss"):
        return {"reasoning_effort": THINKING[shape]}
    return {}


def call_model(client, model, rules, text, shape):
    outages = 0
    while True:
        try:
            reply = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": rules}, {"role": "user", "content": text}],
                response_format=response_format(shape),
                max_completion_tokens=LONGEST_ANSWER[shape],
                **model_options(model, shape),
            )
            return reply.choices[0].message.content
        except RateLimitError as error:
            if "per day" in str(error):
                raise DailyLimitReached(f"{model} has used up today's allowance", seconds_to_wait(error)) from error
            time.sleep(seconds_to_wait(error))
        except (APIConnectionError, InternalServerError):
            # A short outage shouldn't end a long run, and a long one shouldn't hang it.
            outages += 1
            if outages == MOST_OUTAGES:
                raise
            time.sleep(SECONDS_AFTER_OUTAGE)


def checked_answer(client, model, rules, text, shape, name):
    """Returns a checked result, or None if the answer is still invalid after one retry."""
    for attempt in (1, 2):
        try:
            return shape.model_validate(json.loads(call_model(client, model, rules, text, shape)))
        except BadRequestError as error:
            # Groq refuses an answer that breaks the JSON shape. Any other 400 is a real fault.
            if "json_validate_failed" not in str(error):
                raise
            print(f"Groq refused the answer for {name}, attempt {attempt}")
        except (json.JSONDecodeError, ValidationError) as error:
            print(f"Invalid answer for {name}, attempt {attempt}: {str(error)[:120]}")
    return None


def analyse_paper(client, model, paper, shape):
    text = paper_text(paper)
    result = checked_answer(client, model, RULES, text, shape, paper["id"])
    conflict = result and tag_conflict(result.market_focus, f"{paper['title']} {paper['abstract']}")
    if not conflict:
        return result
    # A model can misplace a country, so it looks again. Its second answer stands, because this check can be wrong too.
    second_look = f"{text}\n\nYour first tag was {result.market_focus}, but {conflict}. Check it against the list."
    return checked_answer(client, model, RULES, second_look, shape, paper["id"]) or result


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
        else:
            save_failure(conn, paper["id"])
            print(f"No usable answer for {paper['id']}, so this try is logged.")
    print(f"Analysed {done} papers")
    conn.close()


if __name__ == "__main__":
    analyse_all(5)
