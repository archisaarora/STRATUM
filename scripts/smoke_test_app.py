"""Smoke-test every dashboard page headlessly via streamlit.testing.

Runs each page script against the generated sample outputs and fails if
any page raises an exception while rendering. Run from the repo root:

    python scripts/smoke_test_app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

REPO = Path(__file__).resolve().parents[1]
PAGES = [
    REPO / "app" / "STRATUM.py",
    *sorted((REPO / "app" / "pages").glob("*.py")),
]


def main() -> int:
    failures = 0
    for page in PAGES:
        at = AppTest.from_file(str(page), default_timeout=120)
        at.run()
        errors = [str(e.value) for e in at.exception]
        if errors:
            failures += 1
            print(f"[FAIL] {page.name}")
            for e in errors:
                print(f"       {e[:400]}")
        else:
            n_widgets = (len(at.dataframe) + len(getattr(at, 'metric', []))
                         + len(at.markdown))
            print(f"[ ok ] {page.name}  ({n_widgets} rendered elements)")
    if failures:
        print(f"\n{failures} page(s) failing")
        return 1
    print("\nAll dashboard pages render cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
