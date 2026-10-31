import re
from datetime import date, datetime, timezone

import feedparser

from src.config import load_sources
from src.fetch import contact_email, polite_get
from src.models import Paper, clean_text, clean_url, make_id


def new_paper(source, title, authors, abstract, url, doi, published):
    now = datetime.now(timezone.utc)
    return Paper(
        id=make_id(doi, url),
        title=clean_text(title),
        authors=authors,
        abstract=clean_text(abstract),
        url=clean_url(url),
        doi=doi,
        source=source["name"],
        group=source["group"],
        published=published,
        first_seen=now.date().isoformat(),
        fetched_at=now.isoformat(timespec="seconds"),
    )


def split_title(title):
    # NBER puts the authors in the title, after " -- by ".
    if " -- by " in title:
        return title.rsplit(" -- by ", 1)
    return title, ""


def doi_from_url(url):
    match = re.search(r"nber\.org/papers/(w\d+)", url)
    return f"10.3386/{match.group(1)}" if match else ""


def entry_date(entry):
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    return date(*parsed[:3]).isoformat() if parsed else ""


def paper_from_entry(source, entry):
    title, authors = split_title(entry.title)
    if not authors:
        authors = ", ".join(person.get("name", "") for person in entry.get("authors", []))
    url = entry.link
    return new_paper(source, title, authors, entry.get("summary", ""), url, doi_from_url(url), entry_date(entry))


def read_rss(source):
    response = polite_get(source["url"])
    return [paper_from_entry(source, entry) for entry in feedparser.parse(response.content).entries]


def work_date(work):
    # Many publishers give only a year and month, so fall back to the day Crossref got the record.
    parts = (work.get("published") or {}).get("date-parts", [[]])[0]
    if len(parts) == 3:
        return f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
    return (work.get("created") or {}).get("date-time", "")[:10]


def work_authors(work):
    names = [" ".join(filter(None, [person.get("given"), person.get("family")])) for person in work.get("author", [])]
    return ", ".join(names)


def paper_from_work(source, work):
    title = (work.get("title") or [""])[0]
    return new_paper(source, title, work_authors(work), work.get("abstract", ""), work["URL"], work["DOI"], work_date(work))


def read_crossref(source):
    params = {"sort": "created", "order": "desc", "rows": 50}
    if contact_email():
        params["mailto"] = contact_email()
    items = polite_get(source["url"], params=params).json()["message"]["items"]
    return [paper_from_work(source, work) for work in items]


READERS = {"rss": read_rss, "crossref": read_crossref}


def read_source(source):
    return READERS[source.get("api") or source["type"]](source)


if __name__ == "__main__":
    for source in load_sources():
        papers = read_source(source)
        print(source["name"], "gave", len(papers), "papers")
        print(papers[0])
        print()
