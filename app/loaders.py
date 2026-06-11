"""Shared data access for the STRATUM dashboard.

Reads the CSV outputs of scripts/run_local_pipeline.py from either
local-data/outputs (your real data) or sample-data/outputs (the demo
scenario). Analyst review state (reviewed/notes/escalations) persists to
analyst_state.json next to the outputs so it survives restarts.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "transforms-python" / "src"))

TIER_COLORS = {"S": "#a8071a", "A": "#f5222d", "B": "#fa8c16", "C": "#6b7280"}
TIER_LABELS = {"S": "S — critical", "A": "A — elevated",
               "B": "B — monitored", "C": "C — baseline"}
THREAT_COLORSCALE = [
    (0.00, "#2b3036"), (0.25, "#b89216"), (0.50, "#fa8c16"),
    (0.75, "#f5222d"), (1.00, "#a8071a"),
]
PLOTLY_TEMPLATE = "plotly_dark"
PLOTLY_LAYOUT = dict(
    template=PLOTLY_TEMPLATE,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=10, r=10, t=40, b=10),
)


def data_dirs() -> dict[str, Path]:
    options: dict[str, Path] = {}
    real = REPO / "local-data" / "outputs"
    sample = REPO / "sample-data" / "outputs"
    if real.exists():
        options["My data (local-data)"] = real
    if sample.exists():
        options["Demo scenario (sample-data)"] = sample
    return options


def sidebar() -> Path:
    """Common sidebar: data-source picker + pipeline rerun. Returns the
    selected outputs directory."""
    st.sidebar.markdown("## STRATUM")
    st.sidebar.caption("OSINT threat-capability intelligence")
    options = data_dirs()
    if not options:
        st.sidebar.warning("No pipeline outputs found yet.")
        if st.sidebar.button("Generate demo scenario", type="primary"):
            _run_pipeline(sample=True)
            st.rerun()
        st.info(
            "No data yet. Click **Generate demo scenario** in the sidebar, "
            "or run `python scripts/run_local_pipeline.py` after placing "
            "files in local-data/ (see docs/01_DATA_ACQUISITION.md)."
        )
        st.stop()
    label = st.sidebar.radio("Data source", list(options), key="data_source")
    out_dir = options[label]

    sample = "sample-data" in str(out_dir)
    if st.sidebar.button("Re-run pipeline", width="stretch"):
        with st.spinner("Running STRATUM pipeline…"):
            _run_pipeline(sample=sample)
        st.cache_data.clear()
        st.rerun()
    stamp = run_history(out_dir)
    if len(stamp):
        st.sidebar.caption(f"Last run: {stamp.iloc[-1]['run_at'][:19]} UTC")
    return out_dir


def _run_pipeline(sample: bool) -> None:
    cmd = [sys.executable, str(REPO / "scripts" / "run_local_pipeline.py")]
    if sample:
        cmd.append("--sample")
    # Force UTF-8 in the child process — Windows otherwise defaults to
    # cp1252 and chokes on report typography.
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env,
                          encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        st.error(f"Pipeline failed:\n```\n{proc.stderr[-2000:]}\n```")
        st.stop()


def goto_country(country_code: str) -> None:
    """Cross-page navigation: preselect a country and open the deep dive."""
    st.session_state["selected_country"] = country_code
    st.switch_page("pages/2_Country_Deep_Dive.py")


def history_delta(hist: pd.DataFrame, col: str) -> int | None:
    """Change in a run-history metric vs the previous pipeline run."""
    if len(hist) < 2 or col not in hist.columns:
        return None
    return int(hist.iloc[-1][col] - hist.iloc[-2][col])


@st.cache_data(show_spinner=False)
def _read_csv(path_str: str, mtime: float) -> pd.DataFrame:
    return pd.read_csv(path_str, low_memory=False)


def load(out_dir: Path, name: str) -> pd.DataFrame | None:
    path = out_dir / f"{name}.csv"
    if not path.exists():
        return None
    df = _read_csv(str(path), path.stat().st_mtime)
    return df if len(df) else None


def load_signals(out_dir: Path) -> pd.DataFrame | None:
    df = load(out_dir, "threat_signals")
    if df is None:
        return None
    df["supporting_evidence"] = (
        df["supporting_evidence"].fillna("").astype(str).str.split("|"))
    state = analyst_state(out_dir)
    df["reviewed"] = df["signal_id"].map(
        lambda s: state.get(s, {}).get("reviewed", False))
    df["dismissed"] = df["signal_id"].map(
        lambda s: state.get(s, {}).get("dismissed", False))
    df["escalated"] = df["signal_id"].map(
        lambda s: state.get(s, {}).get("escalated", False))
    df["analyst_notes"] = df["signal_id"].map(
        lambda s: state.get(s, {}).get("notes", ""))
    df["priority"] = (df["signal_strength"] * df["confidence_score"]).round(3)
    return df.sort_values("priority", ascending=False)


def load_profiles(out_dir: Path) -> pd.DataFrame | None:
    df = load(out_dir, "score_country_threat_profiles")
    if df is None:
        return None
    df["top_domains_of_concern"] = (
        df["top_domains_of_concern"].fillna("").astype(str)
        .map(lambda s: [d for d in s.split("|") if d]))
    return df


def country_names(out_dir: Path) -> dict[str, str]:
    ref = pd.read_csv(REPO / "reference-data" / "ref_country_iso_lookup.csv")
    return dict(zip(ref["iso3"], ref["country_name"]))


# ----------------------------------------------------------- analyst state
def _state_path(out_dir: Path) -> Path:
    return out_dir / "analyst_state.json"


def analyst_state(out_dir: Path) -> dict:
    path = _state_path(out_dir)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def update_signal_state(out_dir: Path, signal_id: str, **changes) -> None:
    state = analyst_state(out_dir)
    entry = state.setdefault(signal_id, {})
    entry.update(changes)
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    _state_path(out_dir).write_text(json.dumps(state, indent=1), encoding="utf-8")


def run_history(out_dir: Path) -> pd.DataFrame:
    path = out_dir / "run_history.csv"
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame(columns=["run_at", "total_signals", "compound_signals",
                                 "tier_s", "tier_a", "top_country", "top_tai"])


def fmt_money(v: float | None) -> str:
    if v is None or pd.isna(v):
        return "—"
    for unit, div in [("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)]:
        if abs(v) >= div:
            return f"${v / div:,.1f}{unit}"
    return f"${v:,.0f}"


def tier_badge(tier: str) -> str:
    color = TIER_COLORS.get(tier, "#6b7280")
    return (f"<span style='background:{color};color:white;padding:2px 10px;"
            f"border-radius:4px;font-weight:700'>{TIER_LABELS.get(tier, tier)}"
            f"</span>")
