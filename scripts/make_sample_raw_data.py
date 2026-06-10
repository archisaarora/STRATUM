"""Write the synthetic sample scenario as uploadable raw files.

Usage:
    python scripts/make_sample_raw_data.py [out_dir]

Produces one file per raw Foundry dataset under sample-data/ (default).
Upload each file into its dataset (Foundry: dataset > Import > local files;
keep SIPRI/OpenSanctions as files, the CSVs as tabular) to exercise the
entire pipeline before real downloads/API keys are in place.

The planted storyline (see stratum/core/sample_data.py) ends in a compound
signal for IRN — ideal for the demo walkthrough.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]
                       / "transforms-python" / "src"))

from stratum.core import sample_data  # noqa: E402

UPLOAD_TARGETS = {
    "raw_sipri_milex/SIPRI-Milex-data-SAMPLE.xlsx": "file (keep as files)",
    "raw_sipri_arms_transfers/sipri_arms_trade_register_SAMPLE.csv": "file (keep as files)",
    "raw_opensanctions_entities/targets.simple.SAMPLE.csv": "tabular CSV",
    "raw_usaspending_contracts/usaspending_SAMPLE.csv": "tabular CSV",
    "raw_dod_contracts_daily/dod_contracts_SAMPLE.csv": "tabular CSV",
    "raw_comtrade_flows/comtrade_SAMPLE.csv": "tabular CSV",
    "raw_worldbank_indicators/worldbank_SAMPLE.csv": "tabular CSV",
    "raw_gdelt_events/gdelt_country_daily_SAMPLE.csv": "tabular CSV",
    "raw_acled_events/acled_SAMPLE.csv": "tabular CSV",
}


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else (
        Path(__file__).resolve().parents[1] / "sample-data")

    writers = {
        "raw_sipri_milex/SIPRI-Milex-data-SAMPLE.xlsx":
            lambda p: p.write_bytes(sample_data.sipri_milex_workbook()),
        "raw_sipri_arms_transfers/sipri_arms_trade_register_SAMPLE.csv":
            lambda p: p.write_text(sample_data.sipri_arms_csv()),
        "raw_opensanctions_entities/targets.simple.SAMPLE.csv":
            lambda p: p.write_text(sample_data.opensanctions_csv()),
        "raw_usaspending_contracts/usaspending_SAMPLE.csv":
            lambda p: sample_data.usaspending_raw().to_csv(p, index=False),
        "raw_dod_contracts_daily/dod_contracts_SAMPLE.csv":
            lambda p: sample_data.dod_contracts_raw().to_csv(p, index=False),
        "raw_comtrade_flows/comtrade_SAMPLE.csv":
            lambda p: sample_data.comtrade_raw().to_csv(p, index=False),
        "raw_worldbank_indicators/worldbank_SAMPLE.csv":
            lambda p: sample_data.worldbank_raw().to_csv(p, index=False),
        "raw_gdelt_events/gdelt_country_daily_SAMPLE.csv":
            lambda p: sample_data.gdelt_raw().to_csv(p, index=False),
        "raw_acled_events/acled_SAMPLE.csv":
            lambda p: sample_data.acled_raw().to_csv(p, index=False),
    }
    for rel, write in writers.items():
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        write(path)
        print(f"  wrote {path}  -> upload as {UPLOAD_TARGETS[rel]}")
    print(f"\nDone. Upload each file into the matching Foundry raw dataset "
          f"(names = directory names above).")


if __name__ == "__main__":
    main()
