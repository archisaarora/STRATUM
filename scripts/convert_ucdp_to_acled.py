"""Convert a UCDP GED download into the raw_acled_events upload format.

Can't register for ACLED? UCDP GED is free with NO registration:
  1. Go to https://ucdp.uu.se/downloads/
  2. Download "UCDP Georeferenced Event Dataset (GED)" — global CSV
     (the .zip is fine, pandas reads it directly). Optionally also grab
     the monthly "candidate events" CSVs for recency.
  3. Run:
       python scripts/convert_ucdp_to_acled.py path/to/GEDEvent_v25_1.csv.zip
  4. Upload local-data/raw_acled_events.csv to the Foundry dataset
     raw_acled_events. Done — the rest of the pipeline is unchanged.

Multiple input files are concatenated (e.g. GED + candidate months).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "transforms-python" / "src"))

import pandas as pd  # noqa: E402

from stratum import config  # noqa: E402
from stratum.core.parsing.ucdp import parse_ged_to_acled_shape  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    frames = []
    for arg in sys.argv[1:]:
        raw = pd.read_csv(arg, low_memory=False)  # handles .csv and .csv.zip
        frames.append(parse_ged_to_acled_shape(raw))
        print(f"  {arg}: {len(frames[-1]):,} events")
    out = pd.concat(frames, ignore_index=True)
    out = out[pd.to_datetime(out["event_date"], errors="coerce").dt.year
              >= config.HISTORY_START_YEAR]
    out = out.drop_duplicates(subset=["event_id_cnty"])
    dest = REPO / "local-data" / "raw_acled_events.csv"
    dest.parent.mkdir(exist_ok=True)
    out.to_csv(dest, index=False)
    print(f"wrote {len(out):,} events ({config.HISTORY_START_YEAR}+) -> {dest}")
    print("upload this file to the Foundry dataset: raw_acled_events")


if __name__ == "__main__":
    main()
