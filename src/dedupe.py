import re
from difflib import SequenceMatcher

SIMILAR_TITLES = 0.9
SHORTEST_TITLE = 20


def normalise(title):
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", title.lower()).split())


def same_title(first, second):
    # Titles of very different lengths can't match, and this check is far quicker than comparing them.
    if 2 * min(len(first), len(second)) / (len(first) + len(second)) <= SIMILAR_TITLES:
        return False
    matcher = SequenceMatcher(None, first, second, autojunk=False)
    return matcher.quick_ratio() > SIMILAR_TITLES and matcher.ratio() > SIMILAR_TITLES


def find_duplicates(rows):
    """Takes (id, title, source, abstract length) rows and returns {duplicate id: id we keep}."""
    papers = [
        (paper_id, normalise(title), source, length)
        for paper_id, title, source, length in rows
        if length and len(title) >= SHORTEST_TITLE
    ]
    # The longest abstract is kept, so those come first.
    papers.sort(key=lambda paper: (-paper[3], paper[0]))
    duplicates = {}
    for i, (kept_id, kept_title, kept_source, _) in enumerate(papers):
        if kept_id in duplicates:
            continue
        for other_id, other_title, other_source, _ in papers[i + 1:]:
            if other_id in duplicates or other_source == kept_source:
                continue
            if same_title(kept_title, other_title):
                duplicates[other_id] = kept_id
    return duplicates


def mark_duplicates(conn):
    rows = conn.execute("SELECT id, title, source, LENGTH(abstract) FROM papers").fetchall()
    duplicates = find_duplicates(rows)
    conn.execute("UPDATE papers SET duplicate_of = NULL")
    conn.executemany(
        "UPDATE papers SET duplicate_of = ? WHERE id = ?",
        [(kept, other) for other, kept in duplicates.items()],
    )
    conn.commit()
    return duplicates
