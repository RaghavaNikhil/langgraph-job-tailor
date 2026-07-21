"""Fetches a job posting's text from a URL.

Works for career sites that serve the posting as server-rendered HTML
(Greenhouse, Lever, Workday public pages, most company career sites).
Sites that require JavaScript rendering or a login (LinkedIn, Indeed)
will fail with a clear message — paste those into job_description.txt
manually instead.
"""

import re

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

MIN_TEXT_LENGTH = 300

STRIP_TAGS = ["script", "style", "noscript", "svg", "iframe", "form"]
CONTENT_SELECTORS = [
    "main", "article", "[class*=job-description]", "[class*=jobDescription]",
    "[class*=description]", "[id*=job]", "body",
]


class FetchError(Exception):
    """Raised when a posting cannot be extracted from the URL."""


WORKDAY_RE = re.compile(
    r"https://([\w-]+)\.(wd\d+)\.myworkdayjobs\.com/"
    r"(?:[a-z]{2}-[A-Z]{2}/)?([^/?]+)/job/(.+?)(?:\?.*)?$"
)


def _fetch_workday(url: str) -> str:
    """Workday renders postings with JavaScript, but serves the same data
    as JSON from its public CXS endpoint — fetch that instead."""
    m = WORKDAY_RE.match(url)
    if not m:
        raise FetchError(f"Unrecognized Workday URL format: {url}")
    tenant, wd, site, job_path = m.groups()
    api_url = (
        f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/"
        f"{tenant}/{site}/job/{job_path}"
    )
    try:
        resp = requests.get(
            api_url, headers={**HEADERS, "Accept": "application/json"}, timeout=25
        )
        resp.raise_for_status()
        info = resp.json().get("jobPostingInfo", {})
    except (requests.RequestException, ValueError) as exc:
        raise FetchError(f"Workday API fetch failed for {url}: {exc}") from exc

    desc_html = info.get("jobDescription", "")
    text = _clean_text(BeautifulSoup(desc_html, "html.parser").get_text("\n"))
    if len(text) < MIN_TEXT_LENGTH:
        raise FetchError(f"Workday posting at {url} had no readable description.")
    header = [v for v in (info.get("title"), info.get("location")) if v]
    return "\n".join(header + ["", text])


def fetch_job_description(url: str) -> str:
    """Download and extract readable job posting text from a URL."""
    if "myworkdayjobs.com" in url:
        return _fetch_workday(url)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=25)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise FetchError(f"Could not download {url}: {exc}") from exc

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(STRIP_TAGS):
        tag.decompose()

    text = ""
    for selector in CONTENT_SELECTORS:
        node = soup.select_one(selector)
        if node is None:
            continue
        candidate = _clean_text(node.get_text("\n"))
        if len(candidate) >= MIN_TEXT_LENGTH:
            text = candidate
            break

    if len(text) < MIN_TEXT_LENGTH:
        raise FetchError(
            f"Extracted only {len(text)} characters from {url}. The page "
            "likely requires JavaScript or a login (common for LinkedIn/"
            "Indeed). Copy the posting into job_description.txt manually."
        )
    return text


def _clean_text(raw: str) -> str:
    lines = [l.strip() for l in raw.splitlines()]
    text = "\n".join(l for l in lines if l)
    return re.sub(r"\n{3,}", "\n\n", text)
