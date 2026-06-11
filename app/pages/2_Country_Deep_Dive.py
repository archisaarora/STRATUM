"""Country Deep-Dive — full threat profile for one country, including the
declared-vs-material radar (the core STRATUM visual) and the in-app
intelligence report."""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import loaders  # noqa: E402

from stratum.core.report import build_report  # noqa: E402

st.set_page_config(page_title="STRATUM — Country Deep Dive", page_icon="🛰️",
                   layout="wide")
out_dir = loaders.sidebar()

profiles = loaders.load_profiles(out_dir)
signals = loaders.load_signals(out_dir)
cred = loaders.load(out_dir, "score_material_credibility")
flows = loaders.load(out_dir, "feature_comtrade_with_baselines")
milex = loaders.load(out_dir, "clean_sipri_milex")
budget = loaders.load(out_dir, "feature_budget_discrepancy")
velocity = loaders.load(out_dir, "feature_arms_transfer_velocity")
conflict = loaders.load(out_dir, "feature_conflict_intensity_monthly")
intensity = loaders.load(out_dir, "feature_import_intensity")
names = loaders.country_names(out_dir)

st.title("COUNTRY DEEP-DIVE")

candidates: list[str] = []
for df, col in [(profiles, "country_code"), (cred, "country_code"),
                (budget, "country_code")]:
    if df is not None:
        candidates += df[col].dropna().unique().tolist()
if not candidates:
    st.info("Run the pipeline first — no country data available.")
    st.stop()
ordered = (profiles["country_code"].tolist() if profiles is not None else [])
ordered += sorted(set(candidates) - set(ordered))
# Cross-page navigation: other pages set selected_country before switching.
preselect = st.session_state.pop("selected_country", None)
default_idx = ordered.index(preselect) if preselect in ordered else 0
country = st.selectbox("Country", ordered, index=default_idx,
                       format_func=lambda c: f"{names.get(c, c)} ({c})")
cname = names.get(country, country)

prof = None
if profiles is not None:
    match = profiles[profiles["country_code"] == country]
    prof = match.iloc[0] if len(match) else None

# ----------------------------------------------------------- header
h1, h2, h3, h4, h5 = st.columns(5)
if prof is not None:
    h1.markdown(f"### {cname}")
    h1.markdown(loaders.tier_badge(prof["composite_threat_tier"]),
                unsafe_allow_html=True)
    h2.metric("Threat Acceleration Index",
              f"{prof['threat_acceleration_index']:.1f}")
    h3.metric("Credibility score",
              "—" if pd.isna(prof["capability_credibility_score"])
              else f"{prof['capability_credibility_score']:.0f}/100")
    h4.metric("Active signals", int(prof["active_signal_count"]),
              delta=f"{int(prof['compound_signal_count'])} compound",
              delta_color="inverse")
    lead = f"{int(prof['lead_time_min_months'])}–{int(prof['lead_time_max_months'])} mo"
    color = ("🔴" if prof["lead_time_max_months"] < 18 else
             "🟡" if prof["lead_time_max_months"] <= 36 else "🟢")
    h5.metric("Lead-time estimate", f"{color} {lead}",
              help="Estimated months to operational capability in the top "
                   "domain of concern, from contract maturity stages.")
else:
    h1.markdown(f"### {cname}")
    h2.info("No threat profile (no active signals).")

left, right = st.columns(2)

# ------------------------------------------- radar: declared vs material
with left:
    st.subheader("Declared vs Material Evidence")
    if cred is None or cred[cred["country_code"] == country].empty:
        st.info("Needs Comtrade + SIPRI milex data.")
    else:
        c = cred[cred["country_code"] == country]
        latest = c[c["year"] == c["year"].max()]
        domains = latest["domain"].tolist()
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=latest["declared_pctile"], theta=domains, fill="toself",
            name="Declared programs", line_color="#4096ff"))
        fig.add_trace(go.Scatterpolar(
            r=latest["material_pctile"], theta=domains, fill="toself",
            name="Material evidence", line_color="#f5222d"))
        fig.update_layout(
            polar=dict(radialaxis=dict(range=[0, 1], showticklabels=False),
                       bgcolor="rgba(0,0,0,0)"),
            height=420, legend=dict(orientation="h"),
            **loaders.PLOTLY_LAYOUT)
        st.plotly_chart(fig, width="stretch")
        st.caption(
            "Cross-country percentiles, latest year. **Red outside blue = "
            "physical imports run ahead of declared programs** "
            "(under-declaration); blue outside red = announced programs "
            "without material evidence.")

# ------------------------------------------- budget vs material panel
with right:
    st.subheader("Budget vs Material Imports")
    bcol, mcol = st.columns(2)
    if milex is not None:
        m = milex[(milex["country_code"] == country)
                  & (milex["measure"] == "expenditure_current_usd")]
        if len(m):
            fig = px.bar(m, x="year", y="value",
                         title="Declared milex (SIPRI, USD)")
            fig.update_layout(height=200, **loaders.PLOTLY_LAYOUT)
            bcol.plotly_chart(fig, width="stretch")
    if flows is not None:
        f = flows[(flows["reporter_country"] == country)
                  & (flows["flow_direction"] == "import")]
        if len(f):
            by_year = f.groupby("year")["trade_value_usd"].sum().reset_index()
            fig = px.bar(by_year, x="year", y="trade_value_usd",
                         title="Defense-relevant imports (USD)")
            fig.update_layout(height=200, **loaders.PLOTLY_LAYOUT)
            mcol.plotly_chart(fig, width="stretch")
    if budget is not None:
        b = budget[budget["country_code"] == country].dropna(
            subset=["sipri_wb_discrepancy_pct"])
        if len(b):
            fig = px.line(b, x="year", y="sipri_wb_discrepancy_pct",
                          markers=True,
                          title="SIPRI vs World Bank discrepancy (%)")
            fig.add_hline(y=15, line_dash="dot", line_color="#f5222d",
                          annotation_text="flag threshold")
            fig.update_layout(height=200, **loaders.PLOTLY_LAYOUT)
            st.plotly_chart(fig, width="stretch")

# ------------------------------------------- forensics / arms / conflict
t0, t1, t2, t3 = st.tabs(["Import forensics", "Trade flows",
                          "Arms transfers", "Conflict context"])

with t0:
    if flows is None:
        st.info("Needs Comtrade data — run "
                "`python scripts/local_fetch.py comtrade --monitored-only` "
                "(no key required).")
    else:
        fcountry = flows[(flows["reporter_country"] == country)
                         & (flows["flow_direction"] == "import")]
        if fcountry.empty:
            st.caption("No import flows recorded for this country.")
        else:
            # --- covert-acquisition status banner -------------------------
            if intensity is not None:
                icountry = intensity[intensity["country_code"] == country] \
                    .sort_values("year")
                if len(icountry):
                    latest_i = icountry.iloc[-1]
                    if bool(latest_i["covert_acquisition_flag"]):
                        st.error(
                            f"**COVERT-ACQUISITION PATTERN ({int(latest_i['year'])}):** "
                            f"dual-use imports +{latest_i['dual_use_yoy_pct']:.0f}% "
                            f"YoY while direct military imports stayed flat — "
                            f"led by {latest_i['top_dual_use_category']}.")
                    ic1, ic2, ic3 = st.columns(3)
                    ic1.metric(
                        "Import intensity",
                        f"{latest_i['intensity_ratio']:.2f}",
                        help="Defense-relevant imports per $1 of declared "
                             "military budget. High + rising = imports the "
                             "budget doesn't explain.")
                    z = latest_i["intensity_z"]
                    ic2.metric("vs peers",
                               "—" if pd.isna(z) else f"{z:+.1f} σ",
                               help="Z-score of the (log) intensity ratio "
                                    "across all countries this year.")
                    ic3.metric("Dual-use share",
                               f"{latest_i['dual_use_share']:.0%}",
                               help="Share of defense-relevant imports that "
                                    "are dual-use precursors rather than "
                                    "finished military goods.")
                    # dual-use vs direct streams over time
                    streams = icountry.melt(
                        id_vars="year",
                        value_vars=["dual_use_value", "direct_value"],
                        var_name="stream", value_name="value")
                    streams["stream"] = streams["stream"].map({
                        "dual_use_value": "Dual-use precursors",
                        "direct_value": "Direct military goods"})
                    fig = px.bar(streams, x="year", y="value", color="stream",
                                 barmode="group",
                                 color_discrete_map={
                                     "Dual-use precursors": "#f5222d",
                                     "Direct military goods": "#4096ff"},
                                 title="Two import streams: precursors vs "
                                       "finished military goods")
                    fig.update_layout(height=260, legend_title=None,
                                      **loaders.PLOTLY_LAYOUT)
                    st.plotly_chart(fig, width="stretch")
                    st.caption(
                        "Red growing while blue stays flat is the "
                        "under-the-radar pattern: building capability from "
                        "inputs instead of importing visible weapons.")

            # --- per-commodity drill-down --------------------------------
            st.markdown("##### Commodity drill-down")
            ranked = (fcountry.groupby(["hs_code", "commodity_name"])
                      ["anomaly_score"].max().sort_values(ascending=False)
                      .reset_index())
            options = [f"{r.hs_code} — {r.commodity_name}"
                       for r in ranked.itertuples(index=False)]
            pick = st.selectbox("Commodity (sorted by anomaly)", options,
                                key="commodity_pick")
            hs_pick = pick.split(" — ")[0]
            series = fcountry[fcountry["hs_code"].astype(str) == hs_pick] \
                .sort_values("year")
            show_price = st.toggle(
                "Unit price (USD/kg) — flat volume with rising price can "
                "indicate higher-grade material", key="unit_price")
            fig = go.Figure()
            if show_price and series["net_weight_kg"].fillna(0).gt(0).any():
                price = series["trade_value_usd"] / series["net_weight_kg"]
                fig.add_scatter(x=series["year"], y=price, mode="lines+markers",
                                name="unit price (USD/kg)",
                                line=dict(color="#f0b429"))
            else:
                base = series["rolling_avg_3y"]
                fig.add_scatter(x=series["year"], y=base * 1.5, mode="lines",
                                line=dict(width=0), showlegend=False,
                                hoverinfo="skip")
                fig.add_scatter(x=series["year"], y=base, mode="lines",
                                name="3y baseline ±50%", fill="tonexty",
                                fillcolor="rgba(110,118,129,0.25)",
                                line=dict(color="#6b7280", dash="dot"))
                fig.add_scatter(
                    x=series["year"], y=series["trade_value_usd"],
                    mode="lines+markers", name="import value",
                    line=dict(color="#4096ff"),
                    customdata=series[["baseline_deviation_pct",
                                       "anomaly_score"]],
                    hovertemplate="%{x}: $%{y:,.0f}<br>vs baseline: "
                                  "%{customdata[0]:+.0f}%%<br>anomaly: "
                                  "%{customdata[1]:.2f}<extra></extra>")
                anomalous = series[series["anomaly_flag"].fillna(False)]
                if len(anomalous):
                    fig.add_scatter(
                        x=anomalous["year"], y=anomalous["trade_value_usd"],
                        mode="markers", name="anomalous year",
                        marker=dict(color="#f5222d", size=14, symbol="x"))
            fig.update_layout(height=300, **loaders.PLOTLY_LAYOUT)
            st.plotly_chart(fig, width="stretch")

with t1:
    if flows is None:
        st.info("No Comtrade data.")
    else:
        f = flows[flows["reporter_country"] == country].sort_values(
            "anomaly_score", ascending=False)
        st.dataframe(
            f[["year", "hs_code", "commodity_name", "capability_category",
               "flow_direction", "trade_value_usd", "baseline_deviation_pct",
               "anomaly_score", "anomaly_flag"]],
            width="stretch", hide_index=True,
            column_config={
                "trade_value_usd": st.column_config.NumberColumn(
                    "value (USD)", format="compact"),
                "baseline_deviation_pct": st.column_config.NumberColumn(
                    "vs 3y baseline", format="%+.0f%%"),
                "anomaly_score": st.column_config.ProgressColumn(
                    "anomaly", min_value=0, max_value=1, format="%.2f"),
            })
with t2:
    if velocity is None:
        st.info("No SIPRI arms-transfer data (skipped source).")
    else:
        v = velocity[velocity["recipient_country"] == country]
        if v.empty:
            st.caption("No recorded transfers received.")
        else:
            fig = px.bar(v, x="year", y="total_tiv",
                         title="TIV received per year")
            if v["rolling_avg_tiv_3y"].notna().any():
                fig.add_scatter(x=v["year"], y=v["rolling_avg_tiv_3y"],
                                mode="lines", name="3y rolling avg",
                                line=dict(color="#f0b429", dash="dot"))
            fig.update_layout(height=260, **loaders.PLOTLY_LAYOUT)
            st.plotly_chart(fig, width="stretch")
            spikes = v[v["transfer_spike_flag"].fillna(False)]
            if len(spikes):
                st.warning(f"Transfer spike(s) in "
                           f"{', '.join(map(str, spikes['year'].tolist()))}")
with t3:
    if conflict is None:
        st.info("No GDELT/ACLED/UCDP data (skipped source).")
    else:
        cm = conflict[conflict["country_code"] == country]
        if cm.empty:
            st.caption("No conflict events recorded for this country.")
        else:
            fig = px.area(cm, x="month", y="intensity_score",
                          title="Conflict intensity (0–1, global percentile)")
            fig.update_layout(height=260, yaxis_range=[0, 1],
                              **loaders.PLOTLY_LAYOUT)
            st.plotly_chart(fig, width="stretch")

# ------------------------------------------- signals + report
st.subheader("Active signals")
country_signals = (signals[signals["country_code"] == country]
                   if signals is not None else pd.DataFrame())
if len(country_signals) == 0:
    st.caption("No signals for this country.")
else:
    for r in country_signals.itertuples(index=False):
        flag = "🟣 " if r.signal_type == "compound_signal" else ""
        with st.expander(
                f"{flag}[{r.signal_type}] {r.domain} — strength "
                f"{r.signal_strength:.2f}, confidence {r.confidence_score:.2f}"):
            st.write(r.description_text)
            st.caption(f"window: {r.window_end} · evidence: "
                       f"{', '.join(r.supporting_evidence) or '—'}")

    st.subheader("Intelligence report")
    if st.button("Generate intelligence report", type="primary"):
        evidence = None
        if flows is not None:
            evidence = flows[(flows["reporter_country"] == country)
                             & flows["anomaly_flag"].fillna(False)]
        report = build_report(
            country_signals, country_name=cname,
            profile=prof.to_dict() if prof is not None else None,
            evidence_flows=evidence)
        st.markdown("---")
        st.markdown(report)
        st.download_button("Download report (.md)", report,
                           file_name=f"intel_report_{country}.md")
