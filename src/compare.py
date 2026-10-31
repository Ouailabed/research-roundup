"""Compare hand tags with the AI's tags. Make the sheet, tag it by hand, then score it."""
import csv
import sys

from src.config import ROOT
from src.db import connect

SHEET = ROOT / "data" / "hand_tags.csv"
PAPERS_PER_TAG = {"EM": 8, "DM": 6, "Transversal": 6}
TAGS = set(PAPERS_PER_TAG)


def make_sheet():
    """EM papers are rarer, so the sheet takes more of them. The AI's tags are left out on purpose."""
    conn = connect()
    rows = []
    for focus, count in PAPERS_PER_TAG.items():
        rows += conn.execute(
            """SELECT p.id, p.title, p.abstract FROM papers p JOIN analyses a ON a.paper_id = p.id
            WHERE a.market_focus = ? ORDER BY p.id LIMIT ?""",
            (focus, count),
        ).fetchall()
    conn.close()
    rows.sort(key=lambda row: row["id"])
    # utf-8-sig lets Excel read accents correctly.
    with open(SHEET, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["id", "title", "abstract", "your_tag"])
        writer.writerows([row["id"], row["title"], row["abstract"], ""] for row in rows)
    print(f"Wrote {len(rows)} papers to {SHEET.relative_to(ROOT)}. Fill in your_tag with EM, DM or Transversal.")


def score_sheet():
    conn = connect()
    with open(SHEET, newline="", encoding="utf-8-sig") as file:
        rows = [row for row in csv.DictReader(file) if row["your_tag"].strip() in TAGS]
    misses = []
    for row in rows:
        found = conn.execute(
            "SELECT market_focus, tag_reason FROM analyses WHERE paper_id = ?",
            (row["id"],),
        ).fetchone()
        if found["market_focus"] != row["your_tag"].strip():
            misses.append((row["title"], row["your_tag"].strip(), found["market_focus"], found["tag_reason"]))
    conn.close()
    if not rows:
        print("No hand tags found. Fill in your_tag first.")
        return
    matches = len(rows) - len(misses)
    print(f"The AI matched you on {matches} of {len(rows)} papers: {matches / len(rows):.0%}")
    for title, yours, theirs, reason in misses:
        print(f"- {title}\n  You: {yours}. AI: {theirs}, because: {reason}")


if __name__ == "__main__":
    if sys.argv[1:] == ["sheet"]:
        make_sheet()
    elif sys.argv[1:] == ["score"]:
        score_sheet()
    else:
        print("Use: python -m src.compare sheet, or python -m src.compare score")
