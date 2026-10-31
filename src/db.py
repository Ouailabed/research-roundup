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


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(SCHEMA)
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
