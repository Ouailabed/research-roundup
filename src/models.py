import hashlib
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from ftfy import fix_text

TRACKING_PREFIXES = ("utm_", "fbclid", "gclid")
NO_ABSTRACT = "No abstract is available for this item."


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


def no_em_dash(text):
    return text.replace(" — ", ", ").replace("—", ", ")


def clean_text(text):
    # Some sources escape their tags, so unescape first or the tags slip through.
    without_tags = re.sub(r"</?[a-zA-Z][^>]*>", " ", unescape(text or ""))
    # Some series store text with the wrong encoding, which turns ’ into â€™.
    repaired = fix_text(without_tags, unescape_html=False, uncurl_quotes=False, fix_latin_ligatures=False, fix_character_width=False)
    return " ".join(repaired.split())


def clean_abstract(text):
    text = clean_text(text)
    # Journals start with the word Abstract, and the ECB and the AER end with JEL codes.
    text = re.sub(r"^(?i:abstract|summary)\s*[:.]?\s+(?=[A-Z])", "", text)
    text = re.sub(r"\s*(\(JEL [A-Z0-9, ]+\)|JEL Classification:[A-Z0-9, ]*)\.?$", "", text)
    return "" if text == NO_ABSTRACT else text


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
