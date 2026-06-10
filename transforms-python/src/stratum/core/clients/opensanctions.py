"""OpenSanctions bulk download client.

The consolidated 'default' dataset ships a simple CSV
(targets.simple.csv) — small, no registration. Either download manually
and upload to raw_opensanctions_entities, or let the external transform
fetch it.
"""
from __future__ import annotations

from typing import Any

from stratum.core.http import request_with_retry


def fetch_targets_csv(session: Any, base_url: str, path: str) -> str:
    """Return the raw CSV text of the consolidated targets file."""
    resp = request_with_retry(session, "GET", base_url + path, timeout=300)
    return resp.text
