"""Run the full STRATUM pipeline locally — no Foundry needed.

This is a validation/preview harness: it executes the SAME core logic the
Foundry transforms call, against the files sitting in local-data/ (put
your downloads + local_fetch outputs there). Missing sources are skipped
gracefully. Use it to (a) sanity-check your real files before uploading
them to Foundry and (b) actually see signals/profiles/reports today.

Usage:
    python scripts/run_local_pipeline.py             # run on local-data/
    python scripts/run_local_pipeline.py --sample    # demo on synthetic data
    python scripts/run_local_pipeline.py --input-dir some/other/dir

Recognized inputs (any subset works; matched by filename, searched
recursively under the input dir):
    *.xlsx                       SIPRI milex workbook OR TIV table (auto-detected)
    *arms*.csv / *register*.csv  SIPRI trade-register export
    *comtrade*.csv               raw_comtrade_flows rows (local_fetch comtrade)
    *worldbank*.csv              raw_worldbank_indicators (local_fetch worldbank)
    *usaspending*.csv            raw_usaspending_contracts (local_fetch usaspending)
    *dod*.csv                    raw_dod_contracts_daily (local_fetch dod)
    *acled*.csv                  raw_acled_events (local_fetch acled OR
                                 convert_ucdp_to_acled.py output)
    *gdelt*.csv                  raw_gdelt_events (local_fetch gdelt)
    *opensanctions*.csv / targets.simple*.csv

Outputs land in <input-dir>/outputs/: clean/feature/score CSVs,
threat_signals.csv, country_threat_profiles.csv, and an intelligence
report (markdown) for the top-tier country. Classification uses the
deterministic keyword classifier (the LLM runs in Foundry via AIP).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "transforms-python" / "src"))

import pandas as pd  # noqa: E402

from stratum import config  # noqa: E402
from stratum.core.countries import CountryIndex  # noqa: E402
from stratum.core.features.arms_velocity import transfer_velocity  # noqa: E402
from stratum.core.features.baselines import (  # noqa: E402
    annual_with_baselines, map_capability)
from stratum.core.features.budget import budget_discrepancy  # noqa: E402
from stratum.core.features.conflict import monthly_intensity  # noqa: E402
from stratum.core.features.contracts import (  # noqa: E402
    company_rollup, merge_contract_sources)
from stratum.core.llm.keyword_classifier import (  # noqa: E402
    build_naics_psc_lookup, classify)
from stratum.core.parsing.opensanctions import (  # noqa: E402
    build_org_name_index, tidy_targets)
from stratum.core.parsing.sipri_arms import (  # noqa: E402
    parse_tiv_table, parse_trade_register)
from stratum.core.parsing.sipri_milex import parse_workbook  # noqa: E402
from stratum.core.report import build_report  # noqa: E402
from stratum.core.features.import_intensity import import_intensity  # noqa: E402
from stratum.core.scoring.material_credibility import material_credibility  # noqa: E402
from stratum.core.scoring.procurement_acceleration import (  # noqa: E402
    procurement_acceleration)
from stratum.core.scoring.profiles import country_threat_profiles  # noqa: E402
from stratum.core.scoring.signals import generate_all_signals  # noqa: E402


def say(status: str, msg: str) -> None:
    icon = {"ok": "[+]", "skip": "[-]", "warn": "[!]", "info": "   "}[status]
    print(f"{icon} {msg}")


def find(root: Path, *patterns: str) -> list[Path]:
    hits: list[Path] = []
    for p in patterns:
        hits += [f for f in root.rglob(p) if "outputs" not in f.parts]
    return sorted(set(hits))


def load_inputs(root: Path, idx: CountryIndex):
    """Parse whatever raw files exist into clean-layer frames."""
    data: dict[str, pd.DataFrame | None] = {
        k: None for k in ("milex", "arms", "comtrade", "worldbank",
                          "contracts_usas", "contracts_dod", "acled",
                          "gdelt", "sanctions")}

    milex_frames, tiv_frames = [], []
    for f in find(root, "*.xlsx"):
        content = f.read_bytes()
        try:
            milex_frames.append(parse_workbook(content))
            say("ok", f"SIPRI milex workbook: {f.name}")
            continue
        except ValueError:
            pass
        try:
            tiv_frames.append(parse_tiv_table(content))
            say("ok", f"SIPRI TIV table: {f.name}")
        except ValueError:
            say("warn", f"unrecognized xlsx skipped: {f.name}")
    if milex_frames:
        m = pd.concat(milex_frames, ignore_index=True)
        m, unmatched = idx.standardize_column(m, "country_name_raw", "country_code")
        if len(unmatched):
            say("info", f"milex: {len(unmatched)} unmatched names dropped "
                        f"(e.g. {unmatched.iloc[:3, 0].tolist()})")
        m = m[m["country_code"].notna()
              & (m["year"] >= config.WORLDBANK_START_YEAR)]
        data["milex"] = m

    register_frames = [f for f in tiv_frames if len(f)]
    for f in find(root, "*arms*.csv", "*register*.csv", "*sipri*.csv"):
        try:
            parsed = parse_trade_register(f.read_bytes())
            if len(parsed):
                register_frames.append(parsed)
                say("ok", f"SIPRI arms register: {f.name}")
        except ValueError:
            say("warn", f"not a SIPRI register csv, skipped: {f.name}")
    if register_frames:
        a = pd.concat(register_frames, ignore_index=True)
        a, _ = idx.standardize_column(a, "supplier", "supplier_country")
        a, un = idx.standardize_column(a, "recipient", "recipient_country")
        data["arms"] = a

    def first_csv(*patterns: str, label: str) -> pd.DataFrame | None:
        files = find(root, *patterns)
        if not files:
            say("skip", f"{label}: no file found")
            return None
        frames = [f for f in (pd.read_csv(p, low_memory=False) for p in files)
                  if len(f)]  # drop header-only placeholders before concat
        if not frames:
            say("skip", f"{label}: placeholder/empty file only — skipped")
            return None
        df = (frames[0] if len(frames) == 1
              else pd.concat(frames, ignore_index=True))
        say("ok", f"{label}: {', '.join(f.name for f in files)} "
                  f"({len(df):,} rows)")
        return df

    data["comtrade"] = first_csv("*comtrade*.csv", label="UN Comtrade")
    data["worldbank"] = first_csv("*worldbank*.csv", label="World Bank")
    data["contracts_usas"] = first_csv("*usaspending*.csv", label="USASpending")
    data["contracts_dod"] = first_csv("*dod*.csv", label="defense.gov contracts")
    data["acled"] = first_csv("*acled*.csv", label="ACLED/UCDP events")
    data["gdelt"] = first_csv("*gdelt*.csv", label="GDELT")
    data["sanctions"] = first_csv("*opensanctions*.csv", "targets.simple*.csv",
                                  label="OpenSanctions")
    if data["milex"] is None:
        say("skip", "SIPRI milex: no parseable workbook found")
    if not register_frames:
        say("skip", "SIPRI arms: no register csv / TIV xlsx found")
    return data


def run(root: Path) -> None:
    out_dir = root / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ref = pd.read_csv(REPO / "reference-data" / "ref_country_iso_lookup.csv")
    idx = CountryIndex.from_reference(ref)
    hs_ref = pd.read_csv(REPO / "reference-data" / "ref_hs_capability_mapping.csv")
    naics_ref = pd.read_csv(REPO / "reference-data" / "ref_naics_domain_mapping.csv")

    print(f"\n=== STRATUM local pipeline — inputs from {root} ===")
    d = load_inputs(root, idx)

    def save(df: pd.DataFrame | None, name: str) -> None:
        if df is not None and len(df):
            df.to_csv(out_dir / f"{name}.csv", index=False)

    print("\n--- features ---")
    flows = None
    if d["comtrade"] is not None and len(d["comtrade"]):
        c = d["comtrade"].rename(columns={"reporter_iso3": "reporter_country"})
        c = c[c["hs_code"].notna()].copy()
        c["hs_code"] = c["hs_code"].astype(str).str.split(".").str[0]
        c["flow_direction"] = c["flow_code"].map({"M": "import", "X": "export"})
        c = c[c["flow_direction"].notna()]
        flows = annual_with_baselines(
            map_capability(c, hs_ref),
            window_years=config.ROLLING_BASELINE_YEARS,
            anomaly_flag_pct=config.BASELINE_ANOMALY_FLAG_PCT)
        n_anom = int(flows["anomaly_flag"].fillna(False).sum())
        say("ok", f"commodity baselines: {len(flows):,} series-years, "
                  f"{n_anom} anomalous")
        save(flows, "feature_comtrade_with_baselines")

    budget = None
    if d["milex"] is not None:
        wb = d["worldbank"]
        if wb is not None and "country_iso3" in wb.columns:
            wb = wb.rename(columns={"country_iso3": "country_code"})
        else:
            wb = pd.DataFrame(columns=["country_code", "year",
                                       "indicator_code", "value"])
            say("info", "budget features run without World Bank cross-check")
        budget = budget_discrepancy(
            d["milex"], wb, flag_pct=config.BUDGET_DISCREPANCY_FLAG_PCT)
        n_flag = int(budget["budget_credibility_flag"].fillna(False).sum())
        say("ok", f"budget discrepancy: {len(budget):,} country-years, "
                  f"{n_flag} flagged")
        save(budget, "feature_budget_discrepancy")
        save(d["milex"], "clean_sipri_milex")

    velocity = None
    if d["arms"] is not None:
        a = d["arms"][d["arms"]["recipient_country"].notna()]
        if len(a):
            velocity = transfer_velocity(
                a, window_years=config.ROLLING_BASELINE_YEARS,
                spike_multiplier=config.ARMS_SPIKE_MULTIPLIER)
            say("ok", f"arms velocity: {len(velocity):,} recipient-years, "
                      f"{int(velocity['transfer_spike_flag'].fillna(False).sum())} spikes")
            save(velocity, "feature_arms_transfer_velocity")

    conflict = None
    gdelt_daily = None
    if d["gdelt"] is not None and len(d["gdelt"]):
        g = d["gdelt"]
        g["date"] = pd.to_datetime(g["event_date_int"].astype(str),
                                   format="%Y%m%d", errors="coerce")
        g["country_code"] = g["actor1_country"].map(idx.to_iso3)
        g = g[g["country_code"].notna() & g["date"].notna()]
        gdelt_daily = (g.groupby(["country_code", "date"])
                       .agg(conflict_event_count=("event_count", "sum"),
                            avg_goldstein=("avg_goldstein", "mean"))
                       .reset_index())
    acled_clean = None
    if d["acled"] is not None and len(d["acled"]):
        a = d["acled"].copy()
        a, _ = idx.standardize_column(a, "country", "country_code")
        a = a[a["country_code"].notna()]
        a["fatalities"] = pd.to_numeric(a["fatalities"], errors="coerce").fillna(0)
        acled_clean = a
    if gdelt_daily is not None or acled_clean is not None:
        conflict = monthly_intensity(gdelt_daily, acled_clean)
        say("ok", f"conflict intensity: {len(conflict):,} country-months")
        save(conflict, "feature_conflict_intensity_monthly")

    dod = d["contracts_dod"]
    if dod is not None and "contract_date" not in dod.columns \
            and "announcement_date_text" in dod.columns:
        dod = dod.assign(contract_date=pd.to_datetime(
            dod["announcement_date_text"], format="mixed", errors="coerce"))
    merged = merge_contract_sources(d["contracts_usas"], dod)
    classified = None
    if len(merged):
        lookup = build_naics_psc_lookup(naics_ref)
        results = [
            classify(r.description_raw_text, naics_code=r.naics_code,
                     psc_code=r.psc_code, naics_psc_lookup=lookup)
            for r in merged.itertuples(index=False)
        ]
        merged["capability_domains"] = [r["capability_domains"] for r in results]
        merged["primary_capability_domain"] = [
            r["capability_domains"][0] for r in results]
        merged["technology_keywords"] = [
            r["technology_keywords"] for r in results]
        merged["threat_relevance_score"] = [
            r["threat_relevance_score"] for r in results]
        merged["capability_maturity_stage"] = [
            r["capability_maturity_stage"] for r in results]
        classified = merged
        n_rel = int((merged["primary_capability_domain"] != "none").sum())
        say("ok", f"contracts classified (keyword mode): {len(merged):,} "
                  f"({n_rel:,} capability-relevant)")
        save(classified.drop(columns=["capability_domains",
                                      "technology_keywords"]),
             "feature_contracts_classified")
        if d["sanctions"] is not None:
            companies = company_rollup(
                classified, build_org_name_index(tidy_targets(d["sanctions"])))
            n_s = int(companies["opensanctions_match"].sum())
            say("ok" if not n_s else "warn",
                f"companies: {len(companies):,} "
                f"({n_s} match OpenSanctions entities)")
            save(companies, "feature_companies")

    print("\n--- scores & signals ---")
    credibility = None
    if flows is not None and d["milex"] is not None:
        credibility = material_credibility(flows, d["milex"], classified)
        say("ok", f"material credibility: {len(credibility):,} country-domain-years")
        save(credibility, "score_material_credibility")
    intensity = None
    if flows is not None and d["milex"] is not None:
        intensity = import_intensity(flows, d["milex"])
        n_covert = int(intensity["covert_acquisition_flag"].fillna(False).sum())
        say("warn" if n_covert else "ok",
            f"import intensity: {len(intensity):,} country-years, "
            f"{n_covert} covert-acquisition flags")
        save(intensity, "feature_import_intensity")
    accel = None
    if classified is not None:
        accel = procurement_acceleration(
            classified, count_multiplier=config.ACCEL_COUNT_MULTIPLIER,
            value_growth_pct=config.ACCEL_VALUE_GROWTH_PCT)
        save(accel, "score_procurement_acceleration")

    signals = generate_all_signals(
        flows=flows, accel=accel, budget=budget, credibility=credibility,
        velocity=velocity, intensity=intensity,
        thresholds={
            "material_min_score": config.SIGNAL_MATERIAL_MIN_SCORE,
            "material_min_deviation": config.SIGNAL_MATERIAL_MIN_DEVIATION,
            "underdeclaration_min": config.UNDERDECLARATION_SIGNAL_MIN,
            "compound_escalation": config.COMPOUND_ESCALATION,
        })
    save(signals.assign(supporting_evidence=signals["supporting_evidence"]
                        .map("|".join)) if len(signals) else signals,
         "threat_signals")
    if len(signals):
        say("ok", f"threat signals: {len(signals)} "
                  f"{signals['signal_type'].value_counts().to_dict()}")
    else:
        say("info", "no threat signals fired (need more sources or history "
                    "for baselines)")

    profiles = country_threat_profiles(
        signals, credibility, classified, conflict,
        tier_s=config.TIER_S, tier_a=config.TIER_A, tier_b=config.TIER_B,
        lead_time_bands=config.LEAD_TIME_BANDS)

    # append run history for dashboard tracking
    hist_path = out_dir / "run_history.csv"
    tiers = (profiles["composite_threat_tier"].value_counts()
             if len(profiles) else pd.Series(dtype=int))
    entry = pd.DataFrame([{
        "run_at": pd.Timestamp.now("UTC").isoformat(),
        "total_signals": len(signals),
        "compound_signals": int((signals["signal_type"] == "compound_signal")
                                .sum()) if len(signals) else 0,
        "tier_s": int(tiers.get("S", 0)),
        "tier_a": int(tiers.get("A", 0)),
        "top_country": profiles.iloc[0]["country_code"] if len(profiles) else None,
        "top_tai": profiles.iloc[0]["threat_acceleration_index"]
        if len(profiles) else None,
    }])
    if hist_path.exists():
        entry = pd.concat([pd.read_csv(hist_path), entry], ignore_index=True)
    entry.to_csv(hist_path, index=False)

    if len(profiles):
        save(profiles.assign(top_domains_of_concern=profiles
                             ["top_domains_of_concern"].map("|".join)),
             "score_country_threat_profiles")
        print("\n=== COUNTRY THREAT PROFILES ===")
        show = profiles[["country_code", "composite_threat_tier",
                         "threat_acceleration_index", "active_signal_count",
                         "compound_signal_count", "top_domains_of_concern"]]
        print(show.to_string(index=False))

        top = profiles.iloc[0]
        top_signals = signals[signals.country_code == top["country_code"]]
        report = build_report(
            top_signals, country_name=idx.name_of(top["country_code"]),
            profile=top.to_dict(),
            evidence_flows=(flows[(flows.reporter_country == top["country_code"])
                                  & flows.anomaly_flag.fillna(False)]
                            if flows is not None else None),
        )
        report_path = out_dir / f"intel_report_{top['country_code']}.md"
        report_path.write_text(report, encoding="utf-8")
        say("ok", f"intelligence report -> {report_path}")
    print(f"\nAll outputs in {out_dir}. These are previews — Foundry "
          f"recomputes them from the same raw files you upload.")


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input-dir", default=str(REPO / "local-data"))
    p.add_argument("--sample", action="store_true",
                   help="generate + run the synthetic demo scenario")
    args = p.parse_args()
    if args.sample:
        import subprocess
        sample_dir = REPO / "sample-data"
        subprocess.run([sys.executable,
                        str(REPO / "scripts" / "make_sample_raw_data.py"),
                        str(sample_dir)], check=True, capture_output=True)
        run(sample_dir)
    else:
        run(Path(args.input_dir))


if __name__ == "__main__":
    main()
