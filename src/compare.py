"""Compare hand tags with the AI's tags. Make the sheet, tag it by hand, then score it."""
import csv
import hashlib
import sys
from collections import Counter
from math import sqrt

from src.config import ROOT
from src.db import connect

SHEET = ROOT / "data" / "hand_tags.csv"
SECOND_READER = ROOT / "data" / "second_reader_tags.csv"
PANEL = ROOT / "data" / "reader_panel.csv"
PAPERS_PER_TAG = {"EM": 8, "DM": 6, "Transversal": 6}
TAGS = set(PAPERS_PER_TAG)


def already_tagged():
    if not SECOND_READER.exists():
        return set()
    with open(SECOND_READER, newline="", encoding="utf-8-sig") as file:
        return {row["id"] for row in csv.DictReader(file)}


def shuffled(paper_id):
    # A hash gives a random-looking order that stays the same on every run.
    return hashlib.sha256(paper_id.encode("utf-8")).hexdigest()


def make_sheet():
    """EM papers are rarer, so the sheet takes more of them. The AI's tags are left out on purpose."""
    skip = already_tagged()
    conn = connect()
    rows = []
    for focus, count in PAPERS_PER_TAG.items():
        papers = conn.execute(
            """SELECT p.id, p.title, p.abstract FROM papers p JOIN analyses a ON a.paper_id = p.id
            WHERE a.market_focus = ?""",
            (focus,),
        ).fetchall()
        fresh = [paper for paper in papers if paper["id"] not in skip]
        rows += sorted(fresh, key=lambda paper: shuffled(paper["id"]))[:count]
    conn.close()
    # Mixing the three groups means a paper's place can't give its tag away.
    rows.sort(key=lambda row: shuffled(row["id"]))
    # utf-8-sig lets Excel read accents correctly.
    with open(SHEET, "w", newline="", encoding="utf-8-sig") as file:
        writer = csv.writer(file)
        writer.writerow(["id", "title", "abstract", "your_tag"])
        writer.writerows([row["id"], row["title"], row["abstract"], ""] for row in rows)
    print(f"Wrote {len(rows)} papers to {SHEET.relative_to(ROOT)}. Fill in your_tag with EM, DM or Transversal.")


def score_panel():
    """Reports each round of blind AI readers. The file holds the model's tag at the time, so the result can be rechecked."""
    with open(PANEL, newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    print("This is agreement between AIs, not accuracy. No person is involved.")
    for number in sorted({row["round"] for row in rows}):
        group = [row for row in rows if row["round"] == number]
        matches = sum(row["panel"] == row["model"] for row in group)
        low, high = wilson_interval(matches, len(group))
        unanimous = sum(row["literal"] == row["desk"] == row["sceptic"] for row in group)
        print(f"Round {number}: {matches} of {len(group)} papers match: {matches / len(group):.0%}, 95% range {low:.0%} to {high:.0%}. All three readers agreed on {unanimous}.")
        for row in group:
            if row["panel"] != row["model"]:
                print(f"- {row['title']}\n  Readers: {row['panel']}. Model: {row['model']}")


def wilson_interval(matches, total):
    """The 95% range for a share. It stays honest on small samples, where a plain percentage overclaims."""
    z = 1.96
    share = matches / total
    middle = (share + z * z / (2 * total)) / (1 + z * z / total)
    spread = z * sqrt(share * (1 - share) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return middle - spread, middle + spread


def weighted_match(right, seen, shares):
    """The sheet takes extra EM papers, so each tag's result is weighted by how common that tag really is."""
    tags = [tag for tag in seen if seen[tag]]
    return sum(shares[tag] * right[tag] / seen[tag] for tag in tags) / sum(shares[tag] for tag in tags)


def score_sheet():
    conn = connect()
    with open(SHEET, newline="", encoding="utf-8-sig") as file:
        rows = [row for row in csv.DictReader(file) if row["your_tag"].strip() in TAGS]
    misses = []
    right = Counter()
    seen = Counter()
    for row in rows:
        found = conn.execute(
            "SELECT market_focus, tag_reason FROM analyses WHERE paper_id = ?",
            (row["id"],),
        ).fetchone()
        seen[found["market_focus"]] += 1
        if found["market_focus"] == row["your_tag"].strip():
            right[found["market_focus"]] += 1
        else:
            misses.append((row["title"], row["your_tag"].strip(), found["market_focus"], found["tag_reason"]))
    counts = conn.execute("SELECT market_focus, COUNT(*) FROM analyses GROUP BY market_focus").fetchall()
    conn.close()
    if not rows:
        print("No hand tags found. Fill in your_tag first.")
        return
    matches = len(rows) - len(misses)
    low, high = wilson_interval(matches, len(rows))
    print(f"The AI matched you on {matches} of {len(rows)} papers: {matches / len(rows):.0%}, 95% range {low:.0%} to {high:.0%}")
    print("By the AI's tag: " + ", ".join(f"{tag} {right[tag]} of {seen[tag]}" for tag in sorted(seen)))
    print(f"Weighted by how common each tag is: {weighted_match(right, seen, {row[0]: row[1] for row in counts}):.0%}")
    for title, yours, theirs, reason in misses:
        print(f"- {title}\n  You: {yours}. AI: {theirs}, because: {reason}")


if __name__ == "__main__":
    if sys.argv[1:] == ["sheet"]:
        make_sheet()
    elif sys.argv[1:] == ["score"]:
        score_sheet()
    elif sys.argv[1:] == ["panel"]:
        score_panel()
    else:
        print("Use: python -m src.compare sheet, python -m src.compare score, or python -m src.compare panel")
