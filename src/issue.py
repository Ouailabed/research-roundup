import json
import logging
from collections import Counter
from datetime import date, timedelta

from jinja2 import Environment, FileSystemLoader, select_autoescape
from premailer import Premailer

from src.ai import groq_client, have_key, load_settings
from src.analyse import Analysis, DailyLimitReached, analyse_paper
from src.config import ROOT
from src.db import (
    connect,
    count_unscored,
    has_writeup,
    issue_candidates,
    issue_papers,
    month_counts,
    paper_by_id,
    save_issue,
    save_writeup,
    saved_issue,
)

MIN_PAPERS = 5
MAX_PAPERS = 8
MAX_PER_SOURCE = 2
FOCUSES = ("EM", "DM", "Transversal")
ISSUE_FOLDER = ROOT / "site" / "issues"
SELECTION_NOTE = (
    "Each week the agent scores every new paper from 1 to 10 for its use to a markets research team. "
    "Each month it picks the highest scores, at most 2 from any one source, with a mix of EM, DM and "
    "Transversal papers where possible. A paper belongs to the month it was first seen."
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


def render_issue(month, papers, paper_count, source_count):
    environment = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
    html = environment.get_template("newsletter.html").render(
        month_label=month_label(month),
        intro=(
            f"This month the agent read {paper_count} new papers from {source_count} sources. "
            f"These {len(papers)} stood out for a markets research team."
        ),
        papers=papers,
        selection_note=SELECTION_NOTE,
        source_count=source_count,
    )
    # Email apps ignore most style sheets, so the styles are moved onto each element.
    return Premailer(html, keep_style_tags=True, strip_important=False, cssutils_logging_level=logging.CRITICAL).transform()


def build_issue(month=None):
    month = month or last_full_month()
    models = load_settings()["models"]
    conn = connect()
    chosen = saved_issue(conn, month)
    if not chosen:
        chosen = choose_papers(issue_candidates(conn, month))
        if len(chosen) < MIN_PAPERS:
            print(f"{month}: only {len(chosen)} analysed papers, so no issue was built.")
            conn.close()
            return None
        save_issue(conn, month, chosen)
    if not write_up(conn, chosen, models["strong"]):
        conn.close()
        return None
    papers = issue_context(issue_papers(conn, month))
    paper_count, source_count = month_counts(conn, month)
    conn.close()
    ISSUE_FOLDER.mkdir(parents=True, exist_ok=True)
    path = ISSUE_FOLDER / f"{month}.html"
    path.write_text(render_issue(month, papers, paper_count, source_count), encoding="utf-8")
    print(f"Built {path.relative_to(ROOT)} with {len(papers)} papers")
    return path


def months_since(first, last):
    months = []
    year, month = int(first[:4]), int(first[5:7])
    while f"{year:04d}-{month:02d}" <= last:
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def build_missing_issues():
    """Builds any past month that has no issue yet, once all of its papers are scored."""
    for month in months_since(load_settings()["analyse_from"], last_full_month()):
        if (ISSUE_FOLDER / f"{month}.html").exists():
            continue
        conn = connect()
        left = count_unscored(conn, month)
        conn.close()
        if left:
            print(f"{month}: {left} papers still to score, so its issue waits.")
        else:
            build_issue(month)


if __name__ == "__main__":
    build_issue()
