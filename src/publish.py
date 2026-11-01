"""Writes the public site: the home page, and one data file it reads to explore the papers."""
import json
import shutil

from src.config import ROOT
from src.db import connect, latest_health

SITE = ROOT / "site"


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
        # Models write "Inflation" and "inflation", which would be two topics in the filter.
        paper["topics"] = sorted({topic.strip().lower() for topic in json.loads(paper["topics"])})
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
