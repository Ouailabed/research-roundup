import json
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "roundup.db"
ISSUE_FOLDER = ROOT / "site" / "issues"
FOCUSES = ["EM", "DM", "Transversal"]

st.set_page_config(page_title="The Research Roundup", layout="wide")


@st.cache_data(ttl=600)
def load_papers():
    conn = sqlite3.connect(DB_PATH)
    # A paper chosen for an issue has a full write-up, which replaces its short score text.
    papers = pd.read_sql_query(
        """
        SELECT p.id, p.title, p.authors, p.abstract, p.url, p.doi, p.source, p.source_group,
               p.published, p.first_seen, a.relevance, a.topics,
               COALESCE(w.model, a.model) AS model,
               COALESCE(w.analysed_at, a.analysed_at) AS analysed_at,
               COALESCE(w.summary, a.summary) AS summary,
               COALESCE(w.market_focus, a.market_focus) AS market_focus,
               COALESCE(w.tag_reason, a.tag_reason) AS tag_reason,
               COALESCE(w.takeaways, '[]') AS takeaways,
               COALESCE(w.why_it_matters, '') AS why_it_matters
        FROM papers p
        JOIN analyses a ON a.paper_id = p.id
        LEFT JOIN writeups w ON w.paper_id = p.id
        WHERE p.duplicate_of IS NULL
        """,
        conn,
    )
    issues = pd.read_sql_query("SELECT month, paper_id FROM issues ORDER BY month DESC, position", conn)
    conn.close()
    papers["topics"] = papers["topics"].map(json.loads)
    papers["takeaways"] = papers["takeaways"].map(json.loads)
    months = issues.groupby("paper_id")["month"].apply(list)
    papers["issues"] = papers["id"].map(months).apply(lambda value: value if isinstance(value, list) else [])
    return papers.sort_values(["relevance", "first_seen"], ascending=False).reset_index(drop=True)


@st.cache_data(ttl=600)
def load_health():
    conn = sqlite3.connect(DB_PATH)
    health = pd.read_sql_query("SELECT * FROM health WHERE run_at = (SELECT MAX(run_at) FROM health)", conn)
    conn.close()
    return health


def issue_files():
    return sorted(ISSUE_FOLDER.glob("*.html"), reverse=True)


def month_label(month):
    return date.fromisoformat(f"{month}-01").strftime("%B %Y")


def show_issue(path):
    components.html(path.read_text(encoding="utf-8"), height=1500, scrolling=True)
    st.download_button("Download this issue as HTML", path.read_bytes(), file_name=path.name, mime="text/html")


def latest_issue_page():
    files = issue_files()
    if not files:
        st.info("No issue has been built yet.")
        return
    st.subheader(month_label(files[0].stem))
    show_issue(files[0])


def show_paper(paper):
    st.subheader(paper["title"])
    st.write(paper["authors"])
    st.markdown(f"**{paper['market_focus']}**: {paper['tag_reason']}")
    st.write(paper["summary"])
    if paper["takeaways"]:
        st.markdown("**Key takeaways**")
        for takeaway in paper["takeaways"]:
            st.markdown(f"- {takeaway}")
    if paper["why_it_matters"]:
        st.markdown(f"**Why it matters:** {paper['why_it_matters']}")
    facts = {
        "Source": paper["source"],
        "Published": paper["published"] or "Not given by the source",
        "First seen": paper["first_seen"],
        "Relevance score": f"{paper['relevance']} of 10",
        "Topics": ", ".join(paper["topics"]),
        "In issues": ", ".join(month_label(month) for month in paper["issues"]) or "None",
        "DOI": paper["doi"] or "None",
        "Analysed by": f"{paper['model']} on {paper['analysed_at'][:10]}",
    }
    st.table(pd.Series(facts, name="Value"))
    st.link_button("Open the paper", paper["url"])
    with st.expander("Abstract from the source"):
        st.write(paper["abstract"])


def explore_page():
    papers = load_papers()
    months = sorted({month for value in papers["issues"] for month in value}, reverse=True)
    topics = sorted({topic for value in papers["topics"] for topic in value})

    left, middle, right = st.columns(3)
    chosen_issue = left.selectbox("Issue", ["All papers"] + months, format_func=lambda m: m if m == "All papers" else month_label(m))
    chosen_tags = middle.multiselect("Tag", FOCUSES)
    chosen_sources = right.multiselect("Source", sorted(papers["source"].unique()))
    left, middle, right = st.columns(3)
    chosen_topics = left.multiselect("Topic", topics)
    first = date.fromisoformat(papers["first_seen"].min())
    last = date.fromisoformat(papers["first_seen"].max())
    chosen_dates = middle.date_input("First seen between", (first, last), min_value=first, max_value=last)
    search = right.text_input("Search titles, authors and summaries")

    view = papers
    if chosen_issue != "All papers":
        view = view[view["issues"].map(lambda value: chosen_issue in value)]
    if chosen_tags:
        view = view[view["market_focus"].isin(chosen_tags)]
    if chosen_sources:
        view = view[view["source"].isin(chosen_sources)]
    if chosen_topics:
        view = view[view["topics"].map(lambda value: bool(set(value) & set(chosen_topics)))]
    if len(chosen_dates) == 2:
        start, end = (day.isoformat() for day in chosen_dates)
        view = view[view["first_seen"].between(start, end)]
    if search:
        text = view["title"] + " " + view["authors"] + " " + view["summary"]
        view = view[text.str.contains(search, case=False, regex=False)]

    st.caption(f"{len(view)} of {len(papers)} papers. Click a row to read more.")
    columns = {"relevance": "Score", "market_focus": "Tag", "title": "Title", "source": "Source", "first_seen": "First seen"}
    table = view[list(columns)].rename(columns=columns)
    picked = st.dataframe(table, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row")
    rows = picked.selection.rows
    if rows:
        show_paper(view.iloc[rows[0]])


def archive_page():
    files = issue_files()
    st.subheader("Past issues")
    if files:
        chosen = st.selectbox("Issue", files, format_func=lambda path: month_label(path.stem))
        show_issue(chosen)
    else:
        st.info("No issue has been built yet.")
    st.subheader("Source health report")
    health = load_health()
    st.caption(f"From the last run, on {health['run_at'].iloc[0][:10]}." if len(health) else "No run has been recorded yet.")
    columns = {
        "source": "Source",
        "route": "Route",
        "status": "Status",
        "found": "Found",
        "new": "New",
        "missing_abstracts": "No abstract",
        "note": "Note",
    }
    st.dataframe(health[list(columns)].rename(columns=columns), hide_index=True, width="stretch")


st.title("The Research Roundup")
PAGES = {"Latest issue": latest_issue_page, "Explore papers": explore_page, "Archive": archive_page}
PAGES[st.sidebar.radio("Go to", list(PAGES))]()
