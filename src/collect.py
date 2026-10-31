import os
import re
from datetime import date, datetime, timedelta, timezone

import feedparser
from bs4 import BeautifulSoup

from src.config import load_sources
from src.db import connect, count_missing_abstracts, known_urls, save_health, save_papers
from src.dedupe import mark_duplicates
from src.fetch import contact_email, polite_get, safe_text
from src.health import print_table
from src.models import Paper, clean_text, clean_url, make_id

REPEC_PAPERS_PER_RUN = 30
BACKFILL_ROWS = 200
NBER_DOIS = "https://api.crossref.org/prefixes/10.3386/works"
NBER_LISTING = "https://www.nber.org/api/v1/working_page_listing/contentType/working_paper/_/_/search"


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
    published = entry_date(entry)
    # EconStor dates every paper 1 January, so only the year is real.
    if source.get("year_only"):
        published = published[:4]
    return new_paper(source, title, authors, entry.get("summary", ""), url, doi_from_url(url), published)


def read_rss(source, known):
    response = polite_get(source["url"])
    return [paper_from_entry(source, entry) for entry in feedparser.parse(response.content).entries]


def nber_dates(since):
    # The NBER feed has no dates, but Crossref knows the day each NBER DOI was registered.
    params = {"filter": f"from-created-date:{since}", "rows": 1000, "select": "DOI,created"}
    items = polite_get(NBER_DOIS, params=params).json()["message"]["items"]
    return {item["DOI"].lower(): item["created"]["date-time"][:10] for item in items}


def read_nber_listing(source, dates):
    # The feed can't look back, but the JSON behind NBER's public paper list can.
    papers = []
    for page in range(1, 40):
        params = {"page": page, "perPage": 50, "sortBy": "public_date"}
        results = polite_get(NBER_LISTING, params=params).json()["results"]
        in_range = 0
        for item in results:
            url = f"https://www.nber.org{item['url']}"
            doi = doi_from_url(url)
            if doi in dates:
                in_range += 1
                authors = ", ".join(clean_text(name) for name in item["authors"])
                papers.append(new_paper(source, item["title"], authors, item["abstract"], url, doi, dates[doi]))
        if not in_range:
            break
    return papers


def read_nber(source, known):
    since = source.get("since") or (date.today() - timedelta(days=60)).isoformat()
    dates = nber_dates(since)
    if source.get("since"):
        return read_nber_listing(source, dates)
    papers = read_rss(source, known)
    for paper in papers:
        paper.published = dates.get(paper.id, "")
    return papers


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


def read_crossref(source, known):
    params = {"sort": "created", "order": "desc", "rows": 50}
    if source.get("since"):
        params["filter"] = f"from-created-date:{source['since']}"
        params["rows"] = BACKFILL_ROWS
    if contact_email():
        params["mailto"] = contact_email()
    items = polite_get(source["url"], params=params).json()["message"]["items"]
    # A DOI prefix covers everything a bank publishes, so keep only its working papers.
    wanted = source.get("doi_contains")
    if wanted:
        items = [work for work in items if any(part in work["DOI"].lower() for part in wanted)]
    return [paper_from_work(source, work) for work in items]


def rebuild_abstract(index):
    # OpenAlex stores an abstract as {word: [positions]}, so put the words back in order.
    if not index:
        return ""
    placed = sorted((position, word) for word, positions in index.items() for position in positions)
    return " ".join(word for _, word in placed)


def paper_from_openalex(source, work):
    doi_url = work.get("doi") or ""
    authors = ", ".join(entry["author"]["display_name"] for entry in work.get("authorships", []))
    abstract = rebuild_abstract(work.get("abstract_inverted_index"))
    doi = doi_url.removeprefix("https://doi.org/")
    return new_paper(source, work.get("title") or "", authors, abstract, doi_url or work["id"], doi, work.get("publication_date") or "")


def read_openalex(source, known):
    params = {
        "filter": f"primary_location.source.issn:{source['issn']}",
        "sort": "publication_date:desc",
        "per-page": 50,
    }
    if source.get("since"):
        params["filter"] += f",from_publication_date:{source['since']}"
        params["per-page"] = BACKFILL_ROWS
    if contact_email():
        params["mailto"] = contact_email()
    if os.getenv("OPENALEX_API_KEY"):
        params["api_key"] = os.getenv("OPENALEX_API_KEY")
    results = polite_get(source["url"], params=params).json()["results"]
    return [paper_from_openalex(source, work) for work in results]


def meta_content(soup, name):
    tag = soup.find("meta", attrs={"name": name})
    return (tag.get("content") or "").strip() if tag else ""


def flip_name(name):
    # Some series write names as "Last, First".
    last, comma, first = name.partition(",")
    return f"{first.strip()} {last.strip()}" if comma else name.strip()


def paper_from_repec(source, url):
    soup = BeautifulSoup(polite_get(url).text, "html.parser")
    names = [flip_name(name) for name in meta_content(soup, "citation_authors").split(";")]
    published = meta_content(soup, "citation_publication_date").replace("/", "-")
    return new_paper(source, meta_content(soup, "citation_title"), ", ".join(filter(None, names)), meta_content(soup, "citation_abstract"), url, "", published)


def read_repec(source, known):
    soup = BeautifulSoup(polite_get(source["url"]).text, "html.parser")
    links = [link["href"] for link in soup.select("b > a[href]") if link["href"].startswith("/p/")]
    links = links[:REPEC_PAPERS_PER_RUN]
    source["scanned"] = len(links)
    papers = []
    for href in links:
        url = f"https://ideas.repec.org{href}"
        if url in known:
            continue
        try:
            papers.append(paper_from_repec(source, url))
        except Exception as error:
            print(f"{source['name']}: skipped {url}, {safe_text(error)}")
    return papers


def paper_from_datacite(source, item):
    record = item["attributes"]
    abstracts = [text["description"] for text in record.get("descriptions", []) if text.get("descriptionType") == "Abstract"]
    authors = ", ".join(flip_name(person.get("name", "")) for person in record.get("creators", []))
    title = (record.get("titles") or [{}])[0].get("title", "")
    url = record.get("url") or f"https://doi.org/{record['doi']}"
    return new_paper(source, title, authors, abstracts[0] if abstracts else "", url, record["doi"], (record.get("created") or "")[:10])


def read_datacite(source, known):
    params = {"prefix": source["prefix"], "page[size]": 50, "sort": "-created"}
    items = polite_get(source["url"], params=params).json()["data"]
    wanted = source.get("doi_contains", [""])
    return [paper_from_datacite(source, item) for item in items if any(part in item["attributes"]["doi"].lower() for part in wanted)]


READERS = {
    "rss": read_rss,
    "nber": read_nber,
    "crossref": read_crossref,
    "openalex": read_openalex,
    "repec": read_repec,
    "datacite": read_datacite,
}


def route_of(source):
    return source.get("reader") or source["type"]


def read_source(source, known):
    return READERS[route_of(source)](source, known)


def abstract_on_page(soup):
    heading = soup.find(string=re.compile(r"^\s*Abstract\s*:?\s*$"))
    if not heading:
        return ""
    parts = []
    for node in heading.parent.find_all_next():
        if node.name in ("h1", "h2", "h3", "h4", "footer"):
            break
        if node.name == "p":
            parts.append(node.get_text(" ", strip=True))
    return clean_text(" ".join(parts))


def authors_on_page(soup):
    tags = soup.find_all("meta", attrs={"name": re.compile("^(citation_author|DC.creator)$", re.I)})
    if tags:
        return ", ".join(flip_name(tag.get("content", "")) for tag in tags)
    match = re.search(r"Authors?: (.+?) Series:", " ".join(soup.get_text(" ").split()))
    return match.group(1) if match else ""


def fill_from_pages(source, papers, known):
    # Some feeds leave out the authors or give only the first sentence, so read each new paper's page.
    if not (source.get("abstract_from_page") or source.get("authors_from_page")):
        return
    for paper in papers:
        if paper.url in known:
            continue
        try:
            soup = BeautifulSoup(polite_get(paper.url).text, "html.parser")
            if source.get("abstract_from_page"):
                paper.abstract = abstract_on_page(soup) or paper.abstract
            if source.get("authors_from_page"):
                paper.authors = authors_on_page(soup) or paper.authors
        except Exception as error:
            print(f"{source['name']}: kept the feed text for {paper.url}, {safe_text(error)}")


def collect_source(conn, source, known, run_at):
    row = {
        "run_at": run_at,
        "source": source["name"],
        "source_group": source["group"],
        "route": route_of(source),
        "status": source.get("status", "working"),
        "found": 0,
        "new": 0,
        "missing_abstracts": 0,
        "note": "",
    }
    if row["status"] == "not_covered":
        row["note"] = source["notes"]
        return row
    try:
        papers = read_source(source, known)
        fill_from_pages(source, papers, known)
        row["found"] = source.get("scanned", len(papers))
        row["new"] = save_papers(conn, papers)
        row["missing_abstracts"] = count_missing_abstracts(conn, source["name"])
    except Exception as error:
        row["status"] = "failed"
        row["note"] = safe_text(error)
    return row


def collect_all():
    conn = connect()
    known = known_urls(conn)
    run_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = [collect_source(conn, source, known, run_at) for source in load_sources()]
    save_health(conn, rows)
    print_table(rows)
    print(f"{len(mark_duplicates(conn))} papers are duplicates of another source's paper")
    conn.close()


def best_first_seen(published, fallback, today):
    """A month becomes its first day. A year alone becomes 1 January, so it can't enter a month's issue."""
    if len(published) == 10:
        best = published
    elif len(published) == 7:
        best = f"{published}-01"
    elif len(published) == 4:
        best = f"{published}-01-01"
    else:
        best = fallback
    return min(best, today)


def set_first_seen_from_sources(conn):
    today = date.today().isoformat()
    rows = conn.execute("SELECT id, published, first_seen FROM papers").fetchall()
    conn.executemany(
        "UPDATE papers SET first_seen = ? WHERE id = ?",
        [(best_first_seen(row["published"], row["first_seen"], today), row["id"]) for row in rows],
    )
    conn.commit()


def backfill(since):
    conn = connect()
    known = known_urls(conn)
    for source in load_sources():
        if route_of(source) not in ("crossref", "openalex", "nber"):
            continue
        papers = read_source(dict(source, since=since), known)
        print(f"{source['name']}: {len(papers)} found, {save_papers(conn, papers)} new")
    for doi, day in nber_dates(since).items():
        conn.execute("UPDATE papers SET published = ? WHERE id = ?", (day, doi))
    set_first_seen_from_sources(conn)
    print(f"{len(mark_duplicates(conn))} papers are duplicates of another source's paper")
    conn.close()


if __name__ == "__main__":
    collect_all()
