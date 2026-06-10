"""Fetch real source data from your laptop -> CSVs you upload to Foundry.

This is the zero-Data-Connection path: if you'd rather not (or can't yet)
set up External Transform sources and egress policies, run these commands
locally with your API keys, then upload each output CSV into the matching
Foundry raw dataset. The Foundry clean transforms accept either origin.

Setup:
    pip install pandas requests beautifulsoup4 openpyxl
    # GDELT only:
    pip install google-cloud-bigquery db-dtypes && gcloud auth application-default login

Credentials via env vars (or flags):
    COMTRADE_API_KEY, ACLED_API_KEY + ACLED_EMAIL (or ACLED_ACCESS_TOKEN)

Examples:
    python scripts/local_fetch.py worldbank
    python scripts/local_fetch.py usaspending --start 2020-01-01
    python scripts/local_fetch.py comtrade            # resumable, 450 calls/run
    python scripts/local_fetch.py acled
    python scripts/local_fetch.py gdelt
    python scripts/local_fetch.py opensanctions
    python scripts/local_fetch.py dod --pages 40
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "transforms-python" / "src"))

import pandas as pd  # noqa: E402

from stratum import config, sources  # noqa: E402
from stratum.core.clients import (  # noqa: E402
    acled, comtrade, dod, opensanctions, usaspending, worldbank)
from stratum.core.http import default_session  # noqa: E402

OUT = REPO / "local-data"


def _save(df: pd.DataFrame, name: str) -> None:
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{name}.csv"
    df.to_csv(path, index=False)
    print(f"wrote {len(df):,} rows -> {path}\n  upload to Foundry dataset: {name}")


def cmd_worldbank(args) -> None:
    s = default_session()
    rows = []
    for ind in config.WORLDBANK_INDICATORS:
        rows.extend(worldbank.fetch_indicator(
            s, sources.WORLDBANK_BASE, ind,
            start_year=config.WORLDBANK_START_YEAR, end_year=date.today().year))
    _save(pd.DataFrame(rows), "raw_worldbank_indicators")


def cmd_usaspending(args) -> None:
    s = default_session()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end) if args.end else date.today()
    all_rows = []
    cursor = start
    while cursor < end:
        nxt = min(date(cursor.year + (cursor.month == 12),
                       (cursor.month % 12) + 1, 1) - timedelta(days=1), end)
        records = list(usaspending.iter_awards(
            s, sources.USASPENDING_BASE,
            start_date=cursor.isoformat(), end_date=nxt.isoformat(),
            agencies=config.USASPENDING_AGENCIES,
            award_type_codes=config.USASPENDING_AWARD_TYPES,
            max_pages=args.max_pages))
        all_rows.extend(usaspending.to_raw_rows(
            records, cursor.isoformat(), nxt.isoformat()))
        print(f"  {cursor} .. {nxt}: {len(records)} awards "
              f"(total {len(all_rows):,})")
        cursor = nxt + timedelta(days=1)
    _save(pd.DataFrame(all_rows), "raw_usaspending_contracts")


def cmd_comtrade(args) -> None:
    key = args.key or os.environ.get("COMTRADE_API_KEY")
    if not key:
        sys.exit("set COMTRADE_API_KEY or pass --key")
    s = default_session()
    ckpt_path = OUT / "comtrade_checkpoint.json"
    done = set(map(tuple, json.loads(ckpt_path.read_text()))) \
        if ckpt_path.exists() else set()
    ref = pd.read_csv(REPO / "reference-data" / "ref_country_iso_lookup.csv")
    m49 = dict(zip(ref["iso3"], ref["m49_code"].astype(int)))
    m49.update(config.COMTRADE_SPECIAL_M49)
    reporters = {c: m49[c] for c in config.TARGET_COUNTRIES if c in m49}
    years = list(range(config.HISTORY_START_YEAR, date.today().year + 1))
    queue = comtrade.build_work_queue(reporters, years,
                                      {(c, int(y)) for c, y in done})
    print(f"{len(queue)} (reporter, year) pairs pending; "
          f"processing up to {args.budget} this run")
    rows = []
    for iso3, year in queue[: args.budget]:
        try:
            recs = comtrade.fetch_reporter_year(
                s, sources.COMTRADE_BASE, key,
                reporter_m49=reporters[iso3], year=year,
                hs_codes=config.DEFENSE_HS_CODES)
        except RuntimeError as exc:
            print(f"  {iso3}/{year} FAILED: {exc}")
            continue
        rows.extend(comtrade.to_raw_rows(recs, iso3))
        done.add((iso3, year))
        print(f"  {iso3}/{year}: {len(recs)} rows")
    OUT.mkdir(exist_ok=True)
    ckpt_path.write_text(json.dumps(sorted(done)))
    out_path = OUT / "raw_comtrade_flows.csv"
    df = pd.DataFrame(rows)
    if out_path.exists():
        df = pd.concat([pd.read_csv(out_path), df], ignore_index=True)
    df.to_csv(out_path, index=False)
    print(f"appended -> {out_path} ({len(df):,} total rows). "
          f"Re-run tomorrow until the queue drains.")


def cmd_acled(args) -> None:
    token = args.token or os.environ.get("ACLED_ACCESS_TOKEN")
    key = args.key or os.environ.get("ACLED_API_KEY")
    email = args.email or os.environ.get("ACLED_EMAIL")
    if not token and not (key and email):
        sys.exit("set ACLED_ACCESS_TOKEN, or ACLED_API_KEY + ACLED_EMAIL")
    s = default_session()
    base = sources.ACLED_BASE if token else sources.ACLED_LEGACY_BASE
    rows = acled.fetch_events(
        s, base,
        start_date=f"{config.HISTORY_START_YEAR}-01-01",
        end_date=date.today().isoformat(),
        api_key=key, email=email, bearer_token=token)
    _save(pd.DataFrame(rows), "raw_acled_events")


def cmd_gdelt(args) -> None:
    from stratum.core.clients import gdelt_bq
    start_int = int(f"{config.HISTORY_START_YEAR}0101")
    df = gdelt_bq.fetch_country_daily(start_int)
    _save(df, "raw_gdelt_events")


def cmd_opensanctions(args) -> None:
    s = default_session()
    text = opensanctions.fetch_targets_csv(
        s, sources.OPENSANCTIONS_BASE, sources.OPENSANCTIONS_DEFAULT_PATH)
    OUT.mkdir(exist_ok=True)
    path = OUT / "raw_opensanctions_entities.csv"
    path.write_text(text)
    print(f"wrote {path} — upload to dataset raw_opensanctions_entities")


def cmd_dod(args) -> None:
    s = default_session()
    rows = dod.fetch_recent_contracts(
        s, sources.DEFENSE_GOV_BASE, max_pages=args.pages)
    _save(pd.DataFrame(rows), "raw_dod_contracts_daily")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("worldbank")
    u = sub.add_parser("usaspending")
    u.add_argument("--start", default=f"{config.HISTORY_START_YEAR}-01-01")
    u.add_argument("--end", default=None)
    u.add_argument("--max-pages", type=int, default=400)
    c = sub.add_parser("comtrade")
    c.add_argument("--key", default=None)
    c.add_argument("--budget", type=int, default=config.COMTRADE_DAILY_CALL_BUDGET)
    a = sub.add_parser("acled")
    a.add_argument("--key", default=None)
    a.add_argument("--email", default=None)
    a.add_argument("--token", default=None)
    sub.add_parser("gdelt")
    sub.add_parser("opensanctions")
    d = sub.add_parser("dod")
    d.add_argument("--pages", type=int, default=40)
    args = p.parse_args()
    {"worldbank": cmd_worldbank, "usaspending": cmd_usaspending,
     "comtrade": cmd_comtrade, "acled": cmd_acled, "gdelt": cmd_gdelt,
     "opensanctions": cmd_opensanctions, "dod": cmd_dod}[args.cmd](args)


if __name__ == "__main__":
    main()
