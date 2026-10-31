import hashlib
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PREFIXES = ("utm_", "fbclid", "gclid")


@dataclass
class Paper:
    id: str
    title: str
    authors: str
    abstract: str
    url: str
    doi: str
    source: str
    group: str
    published: str
    first_seen: str
    fetched_at: str


def clean_text(text):
    without_tags = re.sub(r"</?[a-zA-Z][^>]*>", " ", text or "")
    return " ".join(unescape(without_tags).split())


def clean_url(url):
    parts = urlsplit(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith(TRACKING_PREFIXES)
    ]
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def make_id(doi, url):
    if doi:
        return doi.lower()
    return hashlib.sha256(clean_url(url).encode("utf-8")).hexdigest()[:16]
