"""Writes the public site: the home page, and one data file it reads to explore the papers."""
import json
import re
import shutil

from src.config import ROOT
from src.db import connect, latest_health

SITE = ROOT / "site"
SAME_TOPIC = {
    "artificial intelligence": "ai",
    "behavioural economics": "behavioural",
    "climate": "climate change",
    "econometric methods": "econometrics",
    "economic growth": "growth",
    "fiscal": "fiscal policy",
    "labour": "labour markets",
    "labour economics": "labour markets",
    "labour market": "labour markets",
    "macroeconomic": "macroeconomics",
    "monetary": "monetary policy",
}


def clean_topics(topics):
    # Models write "Inflation" and "inflation", or "labor" and "labour", which would be separate filters.
    cleaned = set()
    for topic in topics:
        topic = re.sub(r"\blabor\b", "labour", topic.strip().lower())
        cleaned.add(SAME_TOPIC.get(topic, topic))
    return sorted(cleaned)


def paper_rows(conn):
    # A paper chosen for an issue has a full write-up, which replaces its short score text.
    rows = conn.execute(
        """SELECT p.id, p.title, p.authors, p.source, p.published, p.first_seen, p.url, p.doi,
        a.relevance, a.topics,
        COALESCE(w.model, a.model) AS model,
        COALESCE(w.summary, a.summary) AS summary,
        COALESCE(w.market_focus, a.market_focus) AS market_focus,
        COALESCE(w.tag_reason, a.tag_reason) AS tag_reason,
        COALESCE(w.takeaways, '[]') AS takeaways,
        COALESCE(w.why_it_matters, '') AS why_it_matters
        FROM papers p
        JOIN analyses a ON a.paper_id = p.id
        LEFT JOIN writeups w ON w.paper_id = p.id
        WHERE p.duplicate_of IS NULL
        ORDER BY a.relevance DESC, p.first_seen DESC, p.id"""
    ).fetchall()
    return [dict(row) for row in rows]


def site_data(conn):
    months = {}
    for row in conn.execute("SELECT month, paper_id FROM issues ORDER BY month DESC, position"):
        months.setdefault(row["paper_id"], []).append(row["month"])
    papers = paper_rows(conn)
    for paper in papers:
        paper["topics"] = clean_topics(json.loads(paper["topics"]))
        paper["takeaways"] = json.loads(paper["takeaways"])
        paper["issues"] = months.get(paper["id"], [])
    built = sorted((SITE / "issues").glob("*.html"), reverse=True)
    return {
        "issues": [{"month": path.stem, "file": path.name} for path in built],
        "papers": papers,
        "health": [dict(row) for row in latest_health(conn)],
    }


def publish_site():
    conn = connect()
    data = site_data(conn)
    conn.close()
    (SITE / "data.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    shutil.copyfile(ROOT / "templates" / "index.html", SITE / "index.html")
    print(f"Published {len(data['papers'])} papers and {len(data['issues'])} issues to site")


if __name__ == "__main__":
    publish_site()
