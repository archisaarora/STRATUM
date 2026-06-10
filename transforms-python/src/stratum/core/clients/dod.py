"""defense.gov daily contract announcement scraper.

Listing pages at /News/Contracts/ link to per-day articles whose paragraphs
each describe one contract: contractor, dollar value, narrative, and the
contracting activity. The narrative is richer than USASpending descriptions.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Iterator

from bs4 import BeautifulSoup

from stratum.core.http import request_with_retry
from stratum.core.text import parse_money, stable_id

log = logging.getLogger(__name__)

LISTING_PATH = "/News/Contracts/"
ARTICLE_RE = re.compile(r"/News/Contracts/Contract/Article/(\d+)/?", re.IGNORECASE)
DATE_RE = re.compile(r"(Jan|Feb|March|April|May|June|July|Aug|Sept|Oct|Nov|Dec)[a-z.]*\s+\d{1,2},\s+\d{4}")
BRANCH_HEADERS = {
    "ARMY", "NAVY", "AIR FORCE", "SPACE FORCE", "MARINE CORPS",
    "DEFENSE LOGISTICS AGENCY", "MISSILE DEFENSE AGENCY",
    "DEFENSE ADVANCED RESEARCH PROJECTS AGENCY", "U.S. SPECIAL OPERATIONS COMMAND",
    "DEFENSE INFORMATION SYSTEMS AGENCY", "DEFENSE HEALTH AGENCY",
    "WASHINGTON HEADQUARTERS SERVICES", "DEFENSE THREAT REDUCTION AGENCY",
}
_AWARD_VERBS = re.compile(
    r",?\s+(?:is being awarded|is awarded|has been awarded|was awarded|are awarded)\b",
    re.IGNORECASE,
)


def list_article_urls(session: Any, base_url: str, *, max_pages: int = 10) -> list[str]:
    """Collect article URLs from the paginated listing, newest first."""
    urls: list[str] = []
    seen: set[str] = set()
    for page in range(1, max_pages + 1):
        resp = request_with_retry(
            session, "GET", f"{base_url}{LISTING_PATH}", params={"Page": page}
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        found = 0
        for a in soup.find_all("a", href=True):
            m = ARTICLE_RE.search(a["href"])
            if m and m.group(1) not in seen:
                seen.add(m.group(1))
                href = a["href"]
                urls.append(href if href.startswith("http") else base_url + href)
                found += 1
        if found == 0:
            break
    return urls


def parse_article(html: str, url: str) -> Iterator[dict]:
    """Yield one record per contract paragraph in a daily announcement."""
    soup = BeautifulSoup(html, "html.parser")
    date_text = None
    m = DATE_RE.search(soup.get_text(" ", strip=True)[:4000])
    if m:
        date_text = m.group(0)
    branch = None
    body = soup.find("div", class_=re.compile("body|content", re.IGNORECASE)) or soup
    for p in body.find_all("p"):
        text = p.get_text(" ", strip=True)
        if not text:
            continue
        upper = text.upper().rstrip(":").strip()
        if upper in BRANCH_HEADERS or (len(text) < 60 and upper == text and not any(ch.isdigit() for ch in text)):
            branch = text.title()
            continue
        amount = parse_money(text)
        if amount is None or len(text) < 120:
            continue  # boilerplate / nav / small-print paragraphs
        contractor = _extract_contractor(text)
        activity = _extract_activity(text)
        yield {
            "contract_id": stable_id(url, text[:160], prefix="dod_"),
            "announcement_date_text": date_text,
            "contractor_name": contractor,
            "contract_value_usd": amount,
            "description_text": text,
            "contracting_command": branch,
            "contracting_activity": activity,
            "source_url": url,
        }


def _extract_contractor(text: str) -> str | None:
    m = _AWARD_VERBS.search(text)
    if not m:
        # fallback: "Lockheed Martin Corp., Fort Worth, Texas, ... $x"
        head = text.split(",", 1)[0].strip()
        return head if 3 < len(head) < 120 else None
    head = text[: m.start()]
    # Strip trailing location clauses: "Raytheon Co., Tewksbury, Massachusetts"
    parts = [p.strip() for p in head.split(",") if p.strip()]
    if not parts:
        return None
    # Keep name plus corporate suffix if the split chopped it ("Sierra Nevada Corp")
    name = parts[0]
    if len(parts) > 1 and len(parts[1]) <= 12 and parts[1].rstrip(".").lower() in {
        "inc", "llc", "corp", "co", "ltd", "lp", "llp", "jv"
    }:
        name = f"{name}, {parts[1]}"
    return name[:200]


def _extract_activity(text: str) -> str | None:
    m = re.search(r"([^.]*contracting activity[^.]*)\.", text, re.IGNORECASE)
    return m.group(1).strip()[:300] if m else None


def fetch_recent_contracts(
    session: Any, base_url: str, *, max_pages: int = 10, known_urls: set[str] | None = None
) -> list[dict]:
    known_urls = known_urls or set()
    rows: list[dict] = []
    for url in list_article_urls(session, base_url, max_pages=max_pages):
        if url in known_urls:
            continue
        resp = request_with_retry(session, "GET", url)
        rows.extend(parse_article(resp.text, url))
    log.info("dod scraper: %d contract paragraphs parsed", len(rows))
    return rows
