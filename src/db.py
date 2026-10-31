import sqlite3
from dataclasses import astuple

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
    fetched_at TEXT
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


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    conn.execute(HEALTH_SCHEMA)
    return conn


def known_urls(conn):
    return {row[0] for row in conn.execute("SELECT url FROM papers")}


def save_papers(conn, papers):
    new = 0
    for paper in papers:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO papers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
