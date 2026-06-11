"""Data Health — which sources are loaded, how fresh, and run history."""
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import loaders  # noqa: E402

st.set_page_config(page_title="STRATUM — Data Health", page_icon="🛰️",
                   layout="wide")
out_dir = loaders.sidebar()

st.title("SYSTEM HEALTH & DATA FRESHNESS")

DATASETS = [
    ("clean_sipri_milex", "SIPRI Military Expenditure", "year"),
    ("feature_budget_discrepancy", "Budget discrepancy features", "year"),
    ("feature_comtrade_with_baselines", "UN Comtrade baselines", "year"),
    ("feature_arms_transfer_velocity", "SIPRI arms velocity", "year"),
    ("feature_conflict_intensity_monthly", "Conflict intensity", "month"),
    ("feature_import_intensity", "Import-intensity forensics", "year"),
    ("feature_contracts_classified", "Classified contracts", "award_date"),
    ("feature_companies", "Company rollup", None),
    ("score_material_credibility", "Material credibility", "year"),
    ("score_procurement_acceleration", "Procurement acceleration", None),
    ("threat_signals", "Threat signals", "window_end"),
    ("score_country_threat_profiles", "Country threat profiles", None),
]

rows = []
for name, label, time_col in DATASETS:
    path = out_dir / f"{name}.csv"
    if not path.exists():
        rows.append({"dataset": label, "status": "missing", "rows": 0,
                     "coverage": "—", "updated": "—"})
        continue
    df = pd.read_csv(path, low_memory=False)
    coverage = "—"
    if time_col and time_col in df.columns and len(df):
        vals = df[time_col].dropna().astype(str)
        if len(vals):
            coverage = f"{vals.min()[:10]} → {vals.max()[:10]}"
    rows.append({
        "dataset": label,
        "status": "ok" if len(df) else "empty (skipped source)",
        "rows": len(df),
        "coverage": coverage,
        "updated": datetime.fromtimestamp(
            path.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
    })

health = pd.DataFrame(rows)
st.dataframe(
    health, width="stretch", hide_index=True, height=430,
    column_config={
        "rows": st.column_config.NumberColumn(format="%d"),
        "status": st.column_config.TextColumn(),
    })

ok = int((health["status"] == "ok").sum())
st.caption(f"{ok}/{len(health)} datasets populated. 'Empty' is fine for "
           f"skipped sources (see docs/01, 'Running without "
           f"ACLED / GDELT / SIPRI arms').")

st.subheader("Pipeline run history")
hist = loaders.run_history(out_dir)
if hist.empty:
    st.caption("No runs recorded yet — history starts with the next "
               "pipeline run.")
else:
    st.dataframe(hist.iloc[::-1], width="stretch", hide_index=True)

st.subheader("How to refresh")
st.markdown(
    """
1. **New raw data** → drop files into `local-data/` (or run
   `python scripts/local_fetch.py <source>`).
2. Click **Re-run pipeline** in the sidebar (or run
   `python scripts/run_local_pipeline.py`).
3. Dashboards update automatically; analyst notes and review states are
   keyed to stable signal IDs, so they survive re-runs.
"""
)
