"""HTTP helpers — exponential-backoff retry around a requests-compatible client.

System quality requirement: *all API calls must implement exponential
backoff retry logic*. External Transforms hand us a pre-authenticated
`requests.Session`-like client; locally we build our own. Both flow
through `request_with_retry`.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def default_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": "STRATUM-OSINT/1.0 (research)"})
    return s


def request_with_retry(
    session: Any,
    method: str,
    url: str,
    *,
    max_tries: int = 5,
    base_delay: float = 2.0,
    timeout: int = 120,
    **kwargs: Any,
) -> requests.Response:
    """Issue a request, retrying on transient failures with exponential backoff.

    Delays follow 2s, 4s, 8s, 16s (+ jitter). Raises the last error if all
    tries fail. Honors Retry-After on 429s when present.
    """
    last_exc: Exception | None = None
    for attempt in range(max_tries):
        try:
            resp = session.request(method, url, timeout=timeout, **kwargs)
            if resp.status_code in RETRYABLE_STATUS:
                retry_after = resp.headers.get("Retry-After")
                delay = (
                    float(retry_after)
                    if retry_after and retry_after.isdigit()
                    else base_delay * (2 ** attempt) + random.uniform(0, 1)
                )
                log.warning("HTTP %s from %s (attempt %d/%d) — sleeping %.1fs",
                            resp.status_code, url, attempt + 1, max_tries, delay)
                time.sleep(delay)
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:  # connection errors, timeouts
            last_exc = exc
            delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
            log.warning("Request error on %s (attempt %d/%d): %s — sleeping %.1fs",
                        url, attempt + 1, max_tries, exc, delay)
            time.sleep(delay)
    raise RuntimeError(f"All {max_tries} attempts failed for {url}") from last_exc


def get_json(session: Any, url: str, **kwargs: Any) -> Any:
    return request_with_retry(session, "GET", url, **kwargs).json()


def post_json(session: Any, url: str, **kwargs: Any) -> Any:
    return request_with_retry(session, "POST", url, **kwargs).json()
