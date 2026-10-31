import os

import feedparser
import requests
from dotenv import load_dotenv

load_dotenv()


def headers():
    email = os.getenv("CONTACT_EMAIL", "")
    contact = f"; mailto:{email}" if email else ""
    agent = f"research-roundup/0.1 (+https://github.com/Ouailabed/research-roundup{contact})"
    return {"User-Agent": agent}


def read_feed(url):
    response = requests.get(url, headers=headers(), timeout=30)
    response.raise_for_status()
    return feedparser.parse(response.content).entries


if __name__ == "__main__":
    entries = read_feed("https://www.bis.org/doclist/wppubls.rss")
    for entry in entries:
        print(entry.title, "|", entry.link, "|", entry.get("updated", ""))
    print(len(entries), "papers")
