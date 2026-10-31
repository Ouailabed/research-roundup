import os
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests
from dotenv import load_dotenv

load_dotenv()

AGENT_NAME = "research-roundup"
SECONDS_BETWEEN_REQUESTS = 1

last_request = {}
robots = {}


def contact_email():
    return os.getenv("CONTACT_EMAIL", "")


def headers():
    email = contact_email()
    contact = f"; mailto:{email}" if email else ""
    return {"User-Agent": f"{AGENT_NAME}/0.1 (+https://github.com/Ouailabed/research-roundup{contact})"}


def wait_for_turn(host):
    gap = time.monotonic() - last_request.get(host, 0)
    if gap < SECONDS_BETWEEN_REQUESTS:
        time.sleep(SECONDS_BETWEEN_REQUESTS - gap)
    last_request[host] = time.monotonic()


def robots_for(url):
    parts = urlsplit(url)
    host = parts.netloc
    if host not in robots:
        parser = RobotFileParser()
        wait_for_turn(host)
        response = requests.get(f"{parts.scheme}://{host}/robots.txt", headers=headers(), timeout=30)
        if response.status_code in (401, 403):
            parser.disallow_all = True
        elif response.ok:
            parser.parse(response.text.splitlines())
        else:
            parser.allow_all = True
        robots[host] = parser
    return robots[host]


def polite_get(url, **kwargs):
    if not robots_for(url).can_fetch(AGENT_NAME, url):
        raise PermissionError(f"robots.txt does not allow {url}")
    host = urlsplit(url).netloc
    wait_for_turn(host)
    response = requests.get(url, headers=headers(), timeout=30, **kwargs)
    if not response.ok:
        raise RuntimeError(f"{host} answered {response.status_code}")
    return response


def safe_text(error):
    # requests puts the full URL in its error messages, and the OpenAlex key sits in that URL.
    key = os.getenv("OPENALEX_API_KEY", "")
    return str(error).replace(key, "***") if key else str(error)
