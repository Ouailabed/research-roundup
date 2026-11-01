import hashlib
import json
import logging
import time
from collections import Counter
from datetime import date, timedelta

from jinja2 import Environment, FileSystemLoader, select_autoescape
from premailer import Premailer

from src.ai import groq_client, have_key, load_settings
from src.analyse import Analysis, DailyLimitReached, Overview, Ranking, analyse_paper, checked_answer
from src.config import ROOT
from src.db import (
    connect,
    count_unscored,
    has_writeup,
    issue_candidates,
    issue_papers,
    month_counts,
    paper_by_id,
    papers_to_analyse,
    save_issue,
    save_overview,
    save_writeup,
    saved_issue,
    saved_overview,
)

MIN_PAPERS = 5
MAX_PAPERS = 8
MAX_PER_SOURCE = 2
# A paper can keep failing the checks, and that shouldn't hold up an issue for ever.
MOST_LEFT_UNSCORED = 5
FOCUSES = ("EM", "DM", "Transversal")
# Scores bunch at 9, so the editor reads everything from here up.
EDITOR_SCORE = 9
# A group of 40 fits inside the model's 8,000 tokens a minute.
EDITOR_GROUP = 40
KEPT_FROM_GROUP = 8
KEPT_AT_THE_END = 15
EDITOR_RULES = """You are the editor of The Research Roundup, a monthly newsletter for a markets research team at an investment bank.

Below are new economics papers, numbered, with their EM, DM or Transversal tag. Choose the {keep} most useful to that team and rank them, best first.

Put first the papers with a clear finding that could change a view on rates, currencies, credit, inflation, growth or central bank policy. New evidence beats a survey. A broad finding beats a narrow one. Judge only from the text given.

Answer with the paper numbers in order."""
OVERVIEW_RULES = """You write the opening note of The Research Roundup, a monthly newsletter for a markets research team at an investment bank.

Below are this month's chosen papers. In two or three plain sentences, say what they tell the team and what links them. Don't go through them one by one.

Use only the text given. Never add findings, numbers, names or places that are not there. Never use em dashes."""
ISSUE_FOLDER = ROOT / "site" / "issues"
SELECTION_NOTE = (
    "Each week the agent scores every new paper from 1 to 10 for its use to a markets research team. "
    "Each month a stronger AI model reads the top-scored papers as an editor and ranks them. The issue takes "
    "the top of that ranking, at most 2 from any one source, with a mix of EM, DM and Transversal papers where "
    "possible. A paper belongs to the month it was first seen."
)


def choose_papers(rows):
    """Takes (id, source, market focus, score) rows and returns the ids for one issue.

    The same rows always give the same issue: best score first, then the id to break ties.
    """
    ranked = sorted((tuple(row) for row in rows), key=lambda row: (-row[3], row[0]))
    chosen = []
    per_source = Counter()

    def take(row):
        chosen.append(row)
        per_source[row[1]] += 1

    def fits(row):
        return row not in chosen and per_source[row[1]] < MAX_PER_SOURCE

    # The best paper of each focus goes in first, so the issue has a mix where possible.
    for focus in FOCUSES:
        best = next((row for row in ranked if row[2] == focus and fits(row)), None)
        if best:
            take(best)

    for row in ranked:
        if len(chosen) == MAX_PAPERS:
            break
        if fits(row):
            take(row)

    return [row[0] for row in sorted(chosen, key=lambda row: (-row[3], row[0]))]


def editor_text(rows):
    return "\n\n".join(
        f"{number}. [{row['market_focus']}] {row['title']} ({row['source']})\n{row['summary']}"
        for number, row in enumerate(rows, 1)
    )


def ask_editor(client, model, rows, keep):
    """Returns the rows the editor kept, best first, or None if it gave no usable answer."""
    while True:
        try:
            answer = checked_answer(client, model, EDITOR_RULES.format(keep=keep), editor_text(rows), Ranking, "the editor")
            break
        except DailyLimitReached as error:
            # The ranking only counts once every group is done, so stopping here would waste the calls before it.
            print(f"{error}, so the editor waits {error.seconds:.0f} seconds.", flush=True)
            time.sleep(error.seconds)
    if not answer:
        return None
    numbers = dict.fromkeys(number for number in answer.ranking if 1 <= number <= len(rows))
    return [rows[number - 1] for number in numbers][:keep] or None


def mixed(rows):
    # A hash gives a fixed order that isn't by source, so no group is all from one place.
    return sorted(rows, key=lambda row: hashlib.sha256(row["id"].encode("utf-8")).hexdigest())


def editor_ranking(client, model, rows):
    """Ranks papers, best first. A long list goes through in groups, then the winners are ranked together."""
    finalists = mixed(rows)
    if len(finalists) > EDITOR_GROUP:
        groups = [finalists[start:start + EDITOR_GROUP] for start in range(0, len(finalists), EDITOR_GROUP)]
        finalists = []
        for group in groups:
            winners = ask_editor(client, model, group, KEPT_FROM_GROUP)
            if winners is None:
                return None
            finalists += winners
    return ask_editor(client, model, finalists, KEPT_AT_THE_END)


def editor_order(rows, model, client):
    """Puts the editor's order in place of the score, so that choose_papers applies its rules to that order.

    Two models share the scoring and use the scale a little differently, and many papers tie, so a score
    only earns a place on the editor's desk. With no key or no usable answer, the plain scores decide.
    """
    top = [row for row in rows if row["relevance"] >= EDITOR_SCORE]
    if client is None or len(top) <= MAX_PAPERS:
        return rows
    ranking = editor_ranking(client, model, top)
    if ranking is None:
        print("The editor gave no usable answer, so the plain scores decide this issue.")
        return rows
    places = {row["id"]: place for place, row in enumerate(ranking)}
    return [
        (row["id"], row["source"], row["market_focus"], -places[row["id"]] if row["id"] in places else row["relevance"] - 1000)
        for row in rows
    ]


def last_full_month(today=None):
    first_of_month = (today or date.today()).replace(day=1)
    return (first_of_month - timedelta(days=1)).strftime("%Y-%m")


def month_label(month):
    return date.fromisoformat(f"{month}-01").strftime("%B %Y")


def date_label(published):
    if len(published) == 10:
        day = date.fromisoformat(published)
        return f"{day.day} {day.strftime('%B %Y')}"
    if len(published) == 7:
        return month_label(published)
    return published


def no_em_dash(text):
    return text.replace(" \u2014 ", ", ").replace("\u2014", ", ")


def write_up(conn, paper_ids, model):
    """The stronger model writes the full analysis, only for the chosen papers."""
    missing = [paper_id for paper_id in paper_ids if not has_writeup(conn, paper_id)]
    if not missing:
        return True
    if not have_key():
        print(f"No GROQ_API_KEY found, so {len(missing)} chosen papers have no full analysis.")
        return False
    client = groq_client()
    for paper_id in missing:
        try:
            result = analyse_paper(client, model, paper_by_id(conn, paper_id), Analysis)
        except DailyLimitReached as error:
            print(f"Stopped for today: {error}. Run this again later and it carries on.")
            return False
        if not result:
            print(f"No valid analysis for {paper_id}, so the issue was not built.")
            return False
        save_writeup(conn, paper_id, model, result)
    return True


def write_overview(conn, month, papers, model):
    """The issue's opening note. With no key or no usable answer, the issue builds without one."""
    saved = saved_overview(conn, month)
    if saved or not have_key():
        return saved
    text = "\n\n".join(f"{paper['title']} ({paper['market_focus']})\n{paper['summary']}" for paper in papers)
    answer = checked_answer(groq_client(), model, OVERVIEW_RULES, text, Overview, "the opening note")
    if not answer:
        return ""
    overview = no_em_dash(answer.overview)
    save_overview(conn, month, model, overview)
    return overview


def issue_context(rows):
    papers = []
    for row in rows:
        paper = dict(row)
        paper["title"] = no_em_dash(paper["title"])
        # Some sources date a paper ahead, and a future date looks wrong in an issue.
        paper["published_label"] = date_label(min(paper["published"], paper["first_seen"]))
        paper["summary"] = no_em_dash(paper["summary"])
        paper["takeaways"] = [no_em_dash(line) for line in json.loads(paper["takeaways"])]
        paper["why_it_matters"] = no_em_dash(paper["why_it_matters"])
        paper["tag_reason"] = no_em_dash(paper["tag_reason"])
        papers.append(paper)
    return papers


def render_issue(month, papers, paper_count, source_count, overview=""):
    environment = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
    html = environment.get_template("newsletter.html").render(
        month_label=month_label(month),
        overview=overview,
        intro=(
            f"This month the agent read {paper_count} new papers from {source_count} sources. "
            f"These {len(papers)} stood out for a markets research team."
        ),
        # Inboxes show this next to the subject line.
        preview=f"{len(papers)} papers for {month_label(month)}, led by: {papers[0]['title']}",
        papers=papers,
        selection_note=SELECTION_NOTE,
        source_count=source_count,
        site_url=load_settings()["site_url"],
    )
    # Email apps ignore most style sheets, so the styles are moved onto each element.
    return Premailer(html, keep_style_tags=True, strip_important=False, cssutils_logging_level=logging.CRITICAL).transform()


def build_issue(month=None):
    month = month or last_full_month()
    models = load_settings()["models"]
    conn = connect()
    chosen = saved_issue(conn, month)
    if not chosen:
        left = count_unscored(conn, month)
        if left > MOST_LEFT_UNSCORED:
            print(f"{month}: {left} papers still to score, so its issue waits.")
            conn.close()
            return None
        client = groq_client() if have_key() else None
        chosen = choose_papers(editor_order(issue_candidates(conn, month), models["strong"], client))
        if len(chosen) < MIN_PAPERS:
            print(f"{month}: only {len(chosen)} analysed papers, so no issue was built.")
            conn.close()
            return None
        save_issue(conn, month, chosen)
    if not write_up(conn, chosen, models["strong"]):
        conn.close()
        return None
    papers = issue_context(issue_papers(conn, month))
    try:
        overview = write_overview(conn, month, papers, models["strong"])
    except DailyLimitReached as error:
        print(f"Stopped for today: {error}. Run this again later and it carries on.")
        conn.close()
        return None
    paper_count, source_count = month_counts(conn, month)
    conn.close()
    ISSUE_FOLDER.mkdir(parents=True, exist_ok=True)
    path = ISSUE_FOLDER / f"{month}.html"
    path.write_text(render_issue(month, papers, paper_count, source_count, overview), encoding="utf-8")
    print(f"Built {path.relative_to(ROOT)} with {len(papers)} papers")
    return path


def months_since(first, last):
    months = []
    year, month = int(first[:4]), int(first[5:7])
    while f"{year:04d}-{month:02d}" <= last:
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def is_finished(conn, month):
    # A run that stopped halfway has a list but no page yet.
    return bool(saved_issue(conn, month)) and (ISSUE_FOLDER / f"{month}.html").exists()


def build_missing_issues():
    """Builds any past month with no finished issue."""
    for month in months_since(load_settings()["analyse_from"], last_full_month()):
        conn = connect()
        finished = is_finished(conn, month)
        conn.close()
        if not finished:
            build_issue(month)


def work_left():
    """Counts the papers still to score and the past issues still to build."""
    settings = load_settings()
    conn = connect()
    papers = len(papers_to_analyse(conn, settings["analyse_from"]))
    months = months_since(settings["analyse_from"], last_full_month())
    issues = sum(not is_finished(conn, month) for month in months)
    conn.close()
    return papers + issues


if __name__ == "__main__":
    build_issue()
