"""STRATUM Command Center — global threat landscape at a glance.

Run from the repo root:  streamlit run app/STRATUM.py
Interactions: click a country on the map to open its mini-profile and jump
to the deep dive; click a heat-matrix cell to filter the signal feed.
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
hist = loaders.run_history(out_dir)

st.title("COMMAND CENTER")
st.caption("Global threat capability landscape — open-source derived. "
           "All scores are OSINT estimates, not classified assessments.")

# ----------------------------------------------------------- KPI strip
c1, c2, c3, c4, c5 = st.columns(5)
if profiles is not None:
    tiers = profiles["composite_threat_tier"].value_counts()
    c1.metric("S-tier (critical)", int(tiers.get("S", 0)),
              delta=loaders.history_delta(hist, "tier_s"),
              delta_color="inverse")
    c2.metric("A-tier (elevated)", int(tiers.get("A", 0)),
              delta=loaders.history_delta(hist, "tier_a"),
              delta_color="inverse")
    c3.metric("B-tier (monitored)", int(tiers.get("B", 0)))
if signals is not None:
    c4.metric("Active signals", len(signals),
              delta=loaders.history_delta(hist, "total_signals"),
              delta_color="inverse")
    c5.metric("Compound signals",
              int((signals["signal_type"] == "compound_signal").sum()),
              delta=loaders.history_delta(hist, "compound_signals"),
              delta_color="inverse",
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
        hover_name="country", custom_data=["country_code"],
        hover_data={"composite_threat_tier": True, "top_domain": True,
                    "active_signal_count": True, "country_code": False,
                    "threat_acceleration_index": ":.1f"},
    )
    fig.update_geos(bgcolor="rgba(0,0,0,0)", showcountries=True,
                    countrycolor="#2b3036", showframe=False,
                    landcolor="#11161c", oceancolor="#0b0f14", showocean=True)
    fig.update_layout(height=480, coloraxis_colorbar_title="TAI",
                      clickmode="event+select", **loaders.PLOTLY_LAYOUT)
    map_event = st.plotly_chart(fig, width="stretch",
                                on_select="rerun", key="threat_map")

    clicked = None
    points = (map_event.selection.points
              if map_event and map_event.selection else [])
    if points:
        cd = points[0].get("customdata")
        clicked = cd[0] if cd else points[0].get("location")
    if clicked:
        sel = profiles[profiles["country_code"] == clicked]
        if len(sel):
            r = sel.iloc[0]
            with st.container(border=True):
                p1, p2, p3, p4, p5 = st.columns([2, 1, 1, 2, 1])
                p1.markdown(f"**{names.get(clicked, clicked)}**  "
                            + loaders.tier_badge(r["composite_threat_tier"]),
                            unsafe_allow_html=True)
                p2.metric("TAI", f"{r['threat_acceleration_index']:.1f}")
                p3.metric("Signals", int(r["active_signal_count"]))
                p4.markdown("**Top domains:** "
                            + (", ".join(r["top_domains_of_concern"]) or "—"))
                if p5.button("Open deep dive →", type="primary",
                             key="map_dive"):
                    loaders.goto_country(clicked)
    else:
        st.caption("Click a country on the map to preview its profile and "
                   "jump to the deep dive. Tiers: ≥75 S · ≥50 A · ≥25 B.")

left, right = st.columns([3, 2])

# ----------------------------------------------------------- heat matrix
matrix_filter = st.session_state.get("matrix_filter")
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
                            aspect="auto", text_auto=True,
                            labels=dict(color="signals"))
            fig.update_layout(height=400, coloraxis_showscale=False,
                              **loaders.PLOTLY_LAYOUT)
            hm_event = st.plotly_chart(fig, width="stretch",
                                       on_select="rerun", key="heat_matrix")
            hm_points = (hm_event.selection.points
                         if hm_event and hm_event.selection else [])
            if hm_points:
                p = hm_points[0]
                st.session_state["matrix_filter"] = {
                    "country": p.get("y"), "domain": p.get("x")}
                st.rerun()
            if matrix_filter:
                fc1, fc2 = st.columns([4, 1])
                fc1.info(f"Feed filtered to **{matrix_filter['country']} / "
                         f"{matrix_filter['domain']}**")
                if fc2.button("Clear", key="clear_matrix"):
                    del st.session_state["matrix_filter"]
                    st.rerun()
            else:
                st.caption("Click a cell to filter the signal feed.")

    st.subheader("Signal volume over runs")
    if len(hist) > 1:
        fig = px.line(hist, x="run_at",
                      y=["total_signals", "compound_signals"], markers=True)
        fig.update_layout(height=200, legend_title=None,
                          **loaders.PLOTLY_LAYOUT)
        st.plotly_chart(fig, width="stretch")
    else:
        st.caption("Tracking starts after a second pipeline run.")

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
        view = signals.copy()
        if matrix_filter:
            view = view[(view["country_code"] == matrix_filter["country"])
                        & (view["domain"] == matrix_filter["domain"])]
        if type_sel:
            view = view[view["signal_type"].isin(type_sel)]
        if country_sel:
            view = view[view["country_code"].isin(country_sel)]
        view = view[view["signal_strength"] >= min_strength]
        view["country"] = view["country_code"].map(names)
        feed = st.dataframe(
            view[["country", "domain", "signal_type", "signal_strength",
                  "confidence_score", "window_end", "reviewed",
                  "description_text"]],
            width="stretch", height=380, hide_index=True,
            on_select="rerun", selection_mode="single-row",
            key="signal_feed",
            column_config={
                "signal_strength": st.column_config.ProgressColumn(
                    "strength", min_value=0, max_value=1, format="%.2f"),
                "confidence_score": st.column_config.ProgressColumn(
                    "confidence", min_value=0, max_value=1, format="%.2f"),
                "description_text": st.column_config.TextColumn(
                    "description", width="large"),
            })
        sel_rows = (feed.selection.rows
                    if feed and feed.selection else [])
        if sel_rows:
            r = view.iloc[sel_rows[0]]
            with st.container(border=True):
                st.markdown(f"**[{r['signal_type']}] {r['country']} · "
                            f"{r['domain']}**")
                st.write(r["description_text"])
                st.caption(f"strength {r['signal_strength']:.2f} · confidence "
                           f"{r['confidence_score']:.2f} · evidence: "
                           f"{', '.join(r['supporting_evidence']) or '—'}")
                b1, b2 = st.columns(2)
                if b1.button("Open country deep dive →", key="feed_dive"):
                    loaders.goto_country(r["country_code"])
                b2.page_link("pages/5_Signal_Tracking.py",
                             label="Triage in Signal Tracking →")
        else:
            st.caption("Select a row to expand the signal and jump to its "
                       "country.")
