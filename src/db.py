import json
import sqlite3
from dataclasses import astuple
from datetime import datetime, timezone

from src.config import ROOT

DB_PATH = ROOT / "data" / "roundup.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    authors TEXT,
    abstract TEXT,
    url TEXT,
    doi TEXT,
    source TEXT,
    source_group TEXT,
    published TEXT,
    first_seen TEXT,
    fetched_at TEXT,
    duplicate_of TEXT
)
"""

HEALTH_SCHEMA = """
CREATE TABLE IF NOT EXISTS health (
    run_at TEXT,
    source TEXT,
    source_group TEXT,
    route TEXT,
    status TEXT,
    found INTEGER,
    new INTEGER,
    missing_abstracts INTEGER,
    note TEXT
)
"""

ANALYSES_SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    paper_id TEXT,
    model TEXT,
    analysed_at TEXT,
    summary TEXT,
    takeaways TEXT,
    why_it_matters TEXT,
    market_focus TEXT,
    tag_reason TEXT,
    relevance INTEGER,
    topics TEXT,
    PRIMARY KEY (paper_id, model)
)
"""

ISSUES_SCHEMA = """
CREATE TABLE IF NOT EXISTS issues (
    month TEXT,
    position INTEGER,
    paper_id TEXT,
    PRIMARY KEY (month, paper_id)
)
"""


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    conn.execute(HEALTH_SCHEMA)
    conn.execute(ANALYSES_SCHEMA)
    conn.execute(ISSUES_SCHEMA)
    # A database made before this column existed needs it added.
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(papers)")}
    if "duplicate_of" not in columns:
        conn.execute("ALTER TABLE papers ADD COLUMN duplicate_of TEXT")
    return conn


def known_urls(conn):
    return {row[0] for row in conn.execute("SELECT url FROM papers")}


def save_papers(conn, papers):
    new = 0
    for paper in papers:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO papers
            (id, title, authors, abstract, url, doi, source, source_group, published, first_seen, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            astuple(paper),
        )
        new += cursor.rowcount
    conn.commit()
    return new


def count_missing_abstracts(conn, source):
    return conn.execute("SELECT COUNT(*) FROM papers WHERE source = ? AND abstract = ''", (source,)).fetchone()[0]


def save_health(conn, rows):
    conn.executemany(
        """INSERT INTO health VALUES
        (:run_at, :source, :source_group, :route, :status, :found, :new, :missing_abstracts, :note)""",
        rows,
    )
    conn.commit()


def latest_health(conn):
    return conn.execute("SELECT * FROM health WHERE run_at = (SELECT MAX(run_at) FROM health)").fetchall()


def papers_to_analyse(conn, since):
    """Papers with an abstract and no score yet, newest first."""
    return conn.execute(
        """SELECT id, title, authors, abstract, source FROM papers
        WHERE abstract <> '' AND duplicate_of IS NULL AND first_seen >= ?
        AND id NOT IN (SELECT paper_id FROM analyses)
        ORDER BY first_seen DESC, id""",
        (since,),
    ).fetchall()


def save_analysis(conn, paper_id, model, result):
    data = result.model_dump()
    conn.execute(
        """INSERT OR REPLACE INTO analyses
        (paper_id, model, analysed_at, summary, takeaways, why_it_matters, market_focus, tag_reason, relevance, topics)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            paper_id,
            model,
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            data["summary"],
            json.dumps(data.get("takeaways", [])),
            data.get("why_it_matters", ""),
            data["market_focus"],
            data["tag_reason"],
            data["relevance"],
            json.dumps(data["topics"]),
        ),
    )
    conn.commit()


def issue_candidates(conn, month):
    """A score has no takeaways. Only the full write-up has those."""
    return conn.execute(
        """SELECT p.id, p.source, a.market_focus, a.relevance
        FROM papers p JOIN analyses a ON a.paper_id = p.id
        WHERE a.takeaways = '[]' AND p.duplicate_of IS NULL AND substr(p.first_seen, 1, 7) = ?""",
        (month,),
    ).fetchall()


def saved_issue(conn, month):
    rows = conn.execute("SELECT paper_id FROM issues WHERE month = ? ORDER BY position", (month,))
    return [row[0] for row in rows]


def save_issue(conn, month, paper_ids):
    conn.executemany(
        "INSERT OR REPLACE INTO issues (month, position, paper_id) VALUES (?, ?, ?)",
        [(month, position, paper_id) for position, paper_id in enumerate(paper_ids, 1)],
    )
    conn.commit()


def paper_by_id(conn, paper_id):
    return conn.execute("SELECT id, title, authors, abstract, source FROM papers WHERE id = ?", (paper_id,)).fetchone()


def has_analysis(conn, paper_id, model):
    row = conn.execute("SELECT 1 FROM analyses WHERE paper_id = ? AND model = ?", (paper_id, model)).fetchone()
    return row is not None


def issue_papers(conn, month, model):
    return conn.execute(
        """SELECT p.title, p.authors, p.source, p.published, p.url,
        a.summary, a.takeaways, a.why_it_matters, a.market_focus, a.tag_reason
        FROM issues i JOIN papers p ON p.id = i.paper_id
        JOIN analyses a ON a.paper_id = p.id AND a.model = ?
        WHERE i.month = ? ORDER BY i.position""",
        (model, month),
    ).fetchall()


def month_counts(conn, month):
    return conn.execute(
        """SELECT COUNT(*), COUNT(DISTINCT source) FROM papers
        WHERE substr(first_seen, 1, 7) = ? AND abstract <> '' AND duplicate_of IS NULL""",
        (month,),
    ).fetchone()
