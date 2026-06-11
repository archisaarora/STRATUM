"""Material Credibility Engine — is each country's declared budget
consistent with its physical imports?"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import loaders  # noqa: E402

st.set_page_config(page_title="STRATUM — Material Credibility", page_icon="🛰️",
                   layout="wide")
out_dir = loaders.sidebar()

cred = loaders.load(out_dir, "score_material_credibility")
flows = loaders.load(out_dir, "feature_comtrade_with_baselines")
milex = loaders.load(out_dir, "clean_sipri_milex")
intensity = loaders.load(out_dir, "feature_import_intensity")
profiles = loaders.load_profiles(out_dir)
names = loaders.country_names(out_dir)

st.title("MATERIAL CREDIBILITY ENGINE")
st.caption("Layer 2 — declared budgets cross-referenced against observed "
           "commodity flows. High under-declaration = buying more than the "
           "budget explains; high over-declaration = budget theater.")

if cred is None:
    st.info("Needs Comtrade + SIPRI milex data. Run the pipeline with both "
            "sources present.")
    st.stop()

left, right = st.columns([2, 3])

# ----------------------------------------------------------- leaderboard
with left:
    st.subheader("Country credibility leaderboard")
    latest = cred[cred["year"] == cred.groupby("country_code")["year"]
                  .transform("max")]
    board = (latest.groupby("country_code")
             .agg(credibility=("credibility_score", "mean"),
                  underdeclaration=("underdeclaration_score", "max"),
                  overdeclaration=("overdeclaration_score", "max"))
             .reset_index().sort_values("credibility"))
    board["country"] = board["country_code"].map(names)
    if flows is not None:  # sparkline of defense-relevant import value
        trend = (flows[flows["flow_direction"] == "import"]
                 .groupby(["reporter_country", "year"])["trade_value_usd"]
                 .sum().reset_index().sort_values("year")
                 .groupby("reporter_country")["trade_value_usd"]
                 .apply(list).rename("import_trend"))
        board = board.merge(trend, left_on="country_code",
                            right_index=True, how="left")
    else:
        board["import_trend"] = None
    pick = st.dataframe(
        board[["country", "credibility", "underdeclaration",
               "overdeclaration", "import_trend"]],
        width="stretch", hide_index=True, height=400,
        on_select="rerun", selection_mode="single-row", key="cred_board",
        column_config={
            "credibility": st.column_config.ProgressColumn(
                "credibility", min_value=0, max_value=100, format="%.0f",
                help="100 = declared budget and physical imports tell the "
                     "same story; low = they diverge."),
            "underdeclaration": st.column_config.NumberColumn(
                "under-decl.", format="%.0f",
                help="Imports run AHEAD of declared programs."),
            "overdeclaration": st.column_config.NumberColumn(
                "over-decl.", format="%.0f",
                help="Programs announced without material evidence."),
            "import_trend": st.column_config.LineChartColumn(
                "imports trend", help="Defense-relevant import value by year"),
        })
    sel = pick.selection.rows if pick and pick.selection else []
    if sel:
        chosen = board.iloc[sel[0]]
        if st.button(f"Open deep dive: {chosen['country']} →",
                     type="primary", key="board_dive"):
            loaders.goto_country(chosen["country_code"])

# ----------------------------------------------------------- scatter
with right:
    st.subheader("Budget credibility scatter")
    if flows is None or milex is None:
        st.info("Needs both flows and milex.")
    else:
        imp = flows[flows["flow_direction"] == "import"]
        latest_year = int(imp["year"].max())
        imports = (imp[imp["year"] == latest_year]
                   .groupby("reporter_country")["trade_value_usd"].sum()
                   .reset_index()
                   .rename(columns={"reporter_country": "country_code",
                                    "trade_value_usd": "import_value"}))
        m = milex[(milex["measure"] == "expenditure_current_usd")
                  & (milex["year"] == milex["year"].max())]
        sc = imports.merge(m[["country_code", "value"]], on="country_code")
        sc = sc.rename(columns={"value": "milex_usd"})
        sc = sc[(sc["milex_usd"] > 0) & (sc["import_value"] > 0)]
        if profiles is not None:
            sc = sc.merge(
                profiles[["country_code", "composite_threat_tier"]],
                on="country_code", how="left")
        if "composite_threat_tier" not in sc.columns:
            sc["composite_threat_tier"] = "C"
        sc["composite_threat_tier"] = sc["composite_threat_tier"].fillna("C")
        sc["country"] = sc["country_code"].map(names)
        fig = px.scatter(
            sc, x="milex_usd", y="import_value", log_x=True, log_y=True,
            color="composite_threat_tier", color_discrete_map=loaders.TIER_COLORS,
            hover_name="country", text="country_code",
            labels={"milex_usd": f"Declared milex {latest_year} (USD, log)",
                    "import_value": "Defense-relevant imports (USD, log)"})
        fig.update_traces(textposition="top center")
        # credible-declaration diagonal (constant import/milex ratio)
        lo = float(min(sc["milex_usd"].min(), sc["import_value"].min()))
        hi = float(max(sc["milex_usd"].max(), sc["import_value"].max()))
        ratio = float(np.median(sc["import_value"] / sc["milex_usd"]))
        fig.add_scatter(x=[lo, hi], y=[lo * ratio, hi * ratio],
                        mode="lines", name="expected ratio (median)",
                        line=dict(dash="dot", color="#6b7280"))
        fig.update_layout(height=460, **loaders.PLOTLY_LAYOUT)
        st.plotly_chart(fig, width="stretch")
        st.caption("Points far **above** the line import more defense-"
                   "relevant material than peers with the same declared "
                   "budget (possible under-declaration); far below = "
                   "declared spending without material evidence.")

# ----------------------------------------------------------- covert watch
st.subheader("Covert-acquisition watchlist")
st.caption("Countries whose **dual-use** defense-relevant imports surged "
           "while **direct military** imports and declared budgets stayed "
           "flat — the trade pattern that flies under the radar.")
if intensity is None:
    st.info("Needs Comtrade + SIPRI milex data.")
else:
    watch = intensity[intensity["covert_acquisition_flag"].fillna(False)]
    if watch.empty:
        st.success("No covert-acquisition patterns in the current data.")
    else:
        w = watch.copy()
        w["country"] = w["country_code"].map(names)
        wpick = st.dataframe(
            w[["country", "year", "dual_use_yoy_pct", "direct_yoy_pct",
               "intensity_ratio", "intensity_z", "top_dual_use_category"]],
            width="stretch", hide_index=True,
            on_select="rerun", selection_mode="single-row", key="covert_watch",
            column_config={
                "dual_use_yoy_pct": st.column_config.NumberColumn(
                    "dual-use YoY", format="%+.0f%%"),
                "direct_yoy_pct": st.column_config.NumberColumn(
                    "direct YoY", format="%+.0f%%"),
                "intensity_ratio": st.column_config.NumberColumn(
                    "imports / budget", format="%.2f"),
                "intensity_z": st.column_config.NumberColumn(
                    "vs peers (sigma)", format="%+.1f"),
                "top_dual_use_category": st.column_config.TextColumn(
                    "led by"),
            })
        wsel = wpick.selection.rows if wpick and wpick.selection else []
        if wsel:
            chosen = w.iloc[wsel[0]]
            if st.button(f"Investigate {chosen['country']} in the deep "
                         f"dive →", type="primary", key="covert_dive"):
                loaders.goto_country(chosen["country_code"])

# ----------------------------------------------------------- anomalies
st.subheader("Anomalous flows (the 'what are they buying?' table)")
if flows is None:
    st.info("No flow data.")
else:
    anom = flows[(flows["anomaly_score"].fillna(0) > 0.5)
                 & (flows["flow_direction"] == "import")].copy()
    if anom.empty:
        st.caption("No flows above anomaly score 0.5.")
    else:
        anom["country"] = anom["reporter_country"].map(names)
        st.dataframe(
            anom.sort_values("baseline_deviation_pct", ascending=False)
            [["country", "year", "hs_code", "commodity_name",
              "capability_category", "trade_value_usd",
              "baseline_deviation_pct", "anomaly_score"]],
            width="stretch", hide_index=True,
            column_config={
                "trade_value_usd": st.column_config.NumberColumn(
                    "value (USD)", format="compact"),
                "baseline_deviation_pct": st.column_config.NumberColumn(
                    "vs baseline", format="%+.0f%%"),
                "anomaly_score": st.column_config.ProgressColumn(
                    "anomaly", min_value=0, max_value=1, format="%.2f"),
            })
