"""Fetches a job posting's text from a URL.

Works for career sites that serve the posting as server-rendered HTML
(Greenhouse, Lever, Workday public pages, most company career sites),
plus any site that embeds a schema.org JobPosting JSON-LD block (common
even on JavaScript-heavy sites, since it's there for search engine SEO).
Sites that require JavaScript rendering with no JSON-LD, or a login
(LinkedIn, Indeed), fail with a clear message — paste those into
job_description.txt manually instead.
"""

import json
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
MIN_ALPHA_RATIO = 0.75  # rejects JSON/CSS/JS blobs mistaken for prose

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


def _alpha_ratio(text: str) -> float:
    """Fraction of non-whitespace characters that are letters.

    Real prose runs ~0.9+; JSON/CSS/JS blobs (braces, quotes, hex colors,
    commas) run much lower — used to reject scraped garbage that happens
    to clear the length threshold.
    """
    non_ws = [c for c in text if not c.isspace()]
    if not non_ws:
        return 0.0
    return sum(1 for c in non_ws if c.isalpha()) / len(non_ws)


def _looks_like_prose(text: str) -> bool:
    return len(text) >= MIN_TEXT_LENGTH and _alpha_ratio(text) >= MIN_ALPHA_RATIO


def _extract_json_ld_posting(html: str) -> str:
    """Extract a schema.org JobPosting embedded as JSON-LD, if present.

    Many career sites (including JavaScript single-page apps that render
    no readable body text) still embed this block for search engine SEO,
    making it the most reliable extraction path when available.
    """
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "")
        except (ValueError, TypeError):
            continue
        candidates = data if isinstance(data, list) else data.get("@graph", [data])
        for item in candidates:
            if not isinstance(item, dict):
                continue
            if str(item.get("@type", "")).lower() != "jobposting":
                continue
            desc_html = item.get("description", "")
            desc = _clean_text(
                BeautifulSoup(desc_html, "html.parser").get_text("\n")
            )
            if not _looks_like_prose(desc):
                continue
            org = item.get("hiringOrganization", {})
            org_name = org.get("name") if isinstance(org, dict) else org
            header = [v for v in (item.get("title"), org_name) if v]
            return "\n".join(header + ["", desc])
    return ""


def fetch_job_description(url: str) -> str:
    """Download and extract readable job posting text from a URL."""
    if "myworkdayjobs.com" in url:
        return _fetch_workday(url)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=25)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise FetchError(f"Could not download {url}: {exc}") from exc

    json_ld_text = _extract_json_ld_posting(resp.text)
    if json_ld_text:
        return json_ld_text

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(STRIP_TAGS):
        tag.decompose()

    text = ""
    for selector in CONTENT_SELECTORS:
        node = soup.select_one(selector)
        if node is None:
            continue
        candidate = _clean_text(node.get_text("\n"))
        if _looks_like_prose(candidate):
            text = candidate
            break

    if not text:
        raise FetchError(
            f"Could not extract a readable job posting from {url}. The "
            "page likely requires JavaScript or a login (common for "
            "LinkedIn/Indeed), or has no embedded JobPosting data. Copy "
            "the posting into job_description.txt manually."
        )
    return text


def _clean_text(raw: str) -> str:
    lines = [l.strip() for l in raw.splitlines()]
    text = "\n".join(l for l in lines if l)
    return re.sub(r"\n{3,}", "\n\n", text)
