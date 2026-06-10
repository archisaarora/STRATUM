"""STRATUM Command Center — global threat landscape at a glance.

Run from the repo root:  streamlit run app/STRATUM.py
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import loaders  # noqa: E402

st.set_page_config(page_title="STRATUM — Command Center", page_icon="🛰️",
                   layout="wide")
out_dir = loaders.sidebar()

profiles = loaders.load_profiles(out_dir)
signals = loaders.load_signals(out_dir)
names = loaders.country_names(out_dir)

st.title("COMMAND CENTER")
st.caption("Global threat capability landscape — open-source derived. "
           "All scores are OSINT estimates, not classified assessments.")

# ----------------------------------------------------------- KPI strip
c1, c2, c3, c4, c5 = st.columns(5)
if profiles is not None:
    tiers = profiles["composite_threat_tier"].value_counts()
    c1.metric("S-tier (critical)", int(tiers.get("S", 0)))
    c2.metric("A-tier (elevated)", int(tiers.get("A", 0)))
    c3.metric("B-tier (monitored)", int(tiers.get("B", 0)))
if signals is not None:
    c4.metric("Active signals", len(signals))
    c5.metric("Compound signals",
              int((signals["signal_type"] == "compound_signal").sum()),
              help="Multiple independent indicator types converging on the "
                   "same country & domain — the highest-value alerts.")

# ----------------------------------------------------------- world map
st.subheader("Global Threat Map")
if profiles is None:
    st.info("No country profiles yet — run the pipeline from the sidebar.")
else:
    map_df = profiles.copy()
    map_df["country"] = map_df["country_code"].map(names)
    map_df["top_domain"] = map_df["top_domains_of_concern"].map(
        lambda d: d[0] if d else "—")
    fig = px.choropleth(
        map_df, locations="country_code",
        color="threat_acceleration_index", range_color=(0, 100),
        color_continuous_scale=loaders.THREAT_COLORSCALE,
        hover_name="country",
        hover_data={"composite_threat_tier": True, "top_domain": True,
                    "active_signal_count": True, "country_code": False,
                    "threat_acceleration_index": ":.1f"},
    )
    fig.update_geos(bgcolor="rgba(0,0,0,0)", showcountries=True,
                    countrycolor="#2b3036", showframe=False,
                    landcolor="#11161c", oceancolor="#0b0f14", showocean=True)
    fig.update_layout(height=480, coloraxis_colorbar_title="TAI",
                      **loaders.PLOTLY_LAYOUT)
    st.plotly_chart(fig, width="stretch")
    st.caption("Color = Threat Acceleration Index (0–100). "
               "Tiers: ≥75 S · ≥50 A · ≥25 B · <25 C. "
               "Open **Country Deep Dive** for any country's full profile.")

left, right = st.columns([3, 2])

# ----------------------------------------------------------- signal feed
with left:
    st.subheader("Active Threat Signals")
    if signals is None:
        st.info("No signals generated yet.")
    else:
        f1, f2, f3 = st.columns(3)
        type_sel = f1.multiselect("Signal type",
                                  sorted(signals["signal_type"].unique()))
        country_sel = f2.multiselect(
            "Country", sorted(signals["country_code"].unique()),
            format_func=lambda c: names.get(c, c))
        min_strength = f3.slider("Min strength", 0.0, 1.0, 0.0, 0.05)
        view = signals
        if type_sel:
            view = view[view["signal_type"].isin(type_sel)]
        if country_sel:
            view = view[view["country_code"].isin(country_sel)]
        view = view[view["signal_strength"] >= min_strength]
        st.dataframe(
            view[["country_code", "domain", "signal_type", "signal_strength",
                  "confidence_score", "window_end", "reviewed",
                  "description_text"]],
            width="stretch", height=420, hide_index=True,
            column_config={
                "signal_strength": st.column_config.ProgressColumn(
                    "strength", min_value=0, max_value=1, format="%.2f"),
                "confidence_score": st.column_config.ProgressColumn(
                    "confidence", min_value=0, max_value=1, format="%.2f"),
                "description_text": st.column_config.TextColumn(
                    "description", width="large"),
            })

# ----------------------------------------------------------- heat matrix
with right:
    st.subheader("Domain Heat Matrix")
    if signals is None or signals.empty:
        st.info("—")
    else:
        hm = (signals[signals["domain"] != "defense_general"]
              .groupby(["country_code", "domain"]).size().reset_index(name="n"))
        if hm.empty:
            st.info("No domain-specific signals yet.")
        else:
            pivot = hm.pivot(index="country_code", columns="domain",
                             values="n").fillna(0)
            fig = px.imshow(pivot, color_continuous_scale="YlOrRd",
                            aspect="auto", text_auto=True)
            fig.update_layout(height=420, coloraxis_showscale=False,
                              **loaders.PLOTLY_LAYOUT)
            st.plotly_chart(fig, width="stretch")

    st.subheader("Signal volume over runs")
    hist = loaders.run_history(out_dir)
    if len(hist) > 1:
        fig = px.line(hist, x="run_at",
                      y=["total_signals", "compound_signals"], markers=True)
        fig.update_layout(height=220, legend_title=None,
                          **loaders.PLOTLY_LAYOUT)
        st.plotly_chart(fig, width="stretch")
    else:
        st.caption("Tracking starts after a second pipeline run.")
