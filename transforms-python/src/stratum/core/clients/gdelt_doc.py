"""GDELT DOC 2.0 API — news corroboration for threat signals.

Free, keyless full-text search over the world's news (65 languages,
indexed every 15 minutes). Given a country and a capability domain, we
build a targeted query and return recent article links — the analyst's
"does the world's press corroborate what the trade data shows?" check.

This deliberately replaces raw web scraping: news sites bot-block and
their terms prohibit it, while GDELT exists precisely to be queried.
"""
from __future__ import annotations

import logging
from typing import Any

from stratum.core.http import request_with_retry

log = logging.getLogger(__name__)

DOC_API_BASE = "https://api.gdeltproject.org"
DOC_PATH = "/api/v2/doc/doc"

# Capability domain -> news-language search terms (GDELT query syntax:
# quoted phrases, capitalized OR inside parens).
DOMAIN_NEWS_TERMS: dict[str, str] = {
    "propellants_and_explosives":
        '(propellant OR explosives OR "rocket fuel" OR "missile fuel")',
    "airframe_and_armor_materials":
        '(titanium OR "armor steel" OR airframe OR "missile body")',
    "guidance_and_electronics":
        '("guidance system" OR semiconductors OR radar OR microelectronics)',
    "rare_earth_and_precision_components":
        '("rare earth" OR magnets OR gyroscope)',
    "aircraft_direct": '("combat aircraft" OR "fighter jet" OR warplanes)',
    "naval_direct": '(warship OR frigate OR submarine OR shipyard)',
    "arms_direct": '("arms transfer" OR weapons OR munitions OR ammunition)',
    "fuel_and_logistics": '("fuel stockpile" OR "military logistics")',
    "strategic_reserves": '("gold reserves" OR "strategic reserve")',
    "defense_general":
        '("defense budget" OR "military spending" OR rearmament)',
    "hypersonics": '(hypersonic OR "glide vehicle" OR scramjet)',
    "missile_defense": '("missile defense" OR interceptor OR "air defense")',
    "nuclear": '(nuclear OR enrichment OR warhead)',
    "space_systems": '(satellite OR "space launch" OR anti-satellite)',
    "electronic_warfare": '("electronic warfare" OR jamming)',
    "biodefense": '(biodefense OR "biological weapons" OR pathogen)',
    "autonomous_systems_air": '(drone OR "unmanned aircraft" OR UAV)',
}


def build_query(country_name: str, domain: str) -> str:
    terms = DOMAIN_NEWS_TERMS.get(
        domain, f'("{domain.replace("_", " ")}")')
    return f'"{country_name}" {terms}'


def search_articles(
    session: Any,
    base_url: str = DOC_API_BASE,
    *,
    country_name: str,
    domain: str,
    timespan: str = "12m",
    max_records: int = 30,
) -> list[dict]:
    """Return recent articles as dicts: title, url, source, date, language.

    Deduped to one article per news outlet so a single wire story doesn't
    flood the list.
    """
    params = {
        "query": build_query(country_name, domain),
        "mode": "ArtList",
        "format": "json",
        "maxrecords": max_records,
        "timespan": timespan,
    }
    resp = request_with_retry(session, "GET", base_url + DOC_PATH,
                              params=params, timeout=45)
    try:
        payload = resp.json()
    except ValueError:  # GDELT returns plain-text messages on bad queries
        log.warning("gdelt doc: non-JSON response: %s", resp.text[:200])
        return []
    seen_outlets: set[str] = set()
    out = []
    for a in payload.get("articles", []) or []:
        outlet = a.get("domain", "")
        if outlet in seen_outlets:
            continue
        seen_outlets.add(outlet)
        seen = str(a.get("seendate", ""))
        out.append({
            "title": a.get("title", "(untitled)"),
            "url": a.get("url"),
            "source": outlet,
            "date": (f"{seen[:4]}-{seen[4:6]}-{seen[6:8]}"
                     if len(seen) >= 8 else ""),
            "language": a.get("language", ""),
        })
    log.info("gdelt doc: %d articles for %s/%s", len(out), country_name, domain)
    return out
