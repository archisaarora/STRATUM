"""Procurement Intelligence — Layer 1: classified contract language,
domain velocity, and contractor/sanctions cross-reference."""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import loaders  # noqa: E402

st.set_page_config(page_title="STRATUM — Procurement Intelligence",
                   page_icon="🛰️", layout="wide")
out_dir = loaders.sidebar()

contracts = loaders.load(out_dir, "feature_contracts_classified")
companies = loaders.load(out_dir, "feature_companies")
accel = loaders.load(out_dir, "score_procurement_acceleration")

st.title("PROCUREMENT INTELLIGENCE")
st.caption("Layer 1 — capability signals extracted from contract language. "
           "Locally classified with the keyword model; in Foundry the AIP "
           "LLM takes over with the same taxonomy.")

if contracts is None:
    st.info("No contract data yet — run "
            "`python scripts/local_fetch.py usaspending` (no key needed) "
            "then re-run the pipeline, or switch to the demo scenario.")
    st.stop()

contracts["award_date"] = pd.to_datetime(contracts["award_date"],
                                         errors="coerce")

# ----------------------------------------------------------- filters
f1, f2, f3 = st.columns([2, 2, 3])
domains = sorted(contracts["primary_capability_domain"].dropna().unique())
domain_sel = f1.multiselect("Capability domain",
                            [d for d in domains if d != "none"])
min_value = f2.number_input("Min contract value (USD)", 0, value=0,
                            step=1_000_000)
query = f3.text_input("Search descriptions",
                      placeholder="hypersonic, radar, autonomous…")

view = contracts
if domain_sel:
    view = view[view["primary_capability_domain"].isin(domain_sel)]
else:
    view = view[view["primary_capability_domain"] != "none"]
if min_value:
    view = view[view["total_value_usd"].fillna(0) >= min_value]
if query:
    view = view[view["description_raw_text"].str.contains(
        query, case=False, na=False)]

m1, m2, m3 = st.columns(3)
m1.metric("Capability-relevant contracts", f"{len(view):,}")
m2.metric("Total value", loaders.fmt_money(view["total_value_usd"].sum()))
m3.metric("Avg threat relevance",
          f"{view['threat_relevance_score'].mean():.2f}"
          if len(view) else "—")

# ----------------------------------------------------------- velocity
st.subheader("Domain velocity")
if len(view):
    monthly = (view.dropna(subset=["award_date"])
               .assign(month=lambda d: d["award_date"].dt.to_period("M")
                       .dt.to_timestamp())
               .groupby(["month", "primary_capability_domain"])
               .agg(contracts=("contract_id", "count"),
                    value=("total_value_usd", "sum")).reset_index())
    metric = st.radio("Plot", ["contracts", "value"], horizontal=True,
                      label_visibility="collapsed")
    fig = px.bar(monthly, x="month", y=metric,
                 color="primary_capability_domain")
    fig.update_layout(height=300, legend_title=None, **loaders.PLOTLY_LAYOUT)
    st.plotly_chart(fig, width="stretch")

if accel is not None and len(accel[accel["domain_acceleration_flag"]
                                   .fillna(False)]):
    flagged = accel[accel["domain_acceleration_flag"].fillna(False)]
    st.warning("Acceleration flags: " + " · ".join(
        f"**{r.country_code}/{r.domain}** "
        f"({int(r.contract_count_12m)} awards, 12m)"
        for r in flagged.itertuples(index=False)))

# ----------------------------------------------------------- table
st.subheader("Contracts")
st.dataframe(
    view.sort_values("threat_relevance_score", ascending=False)
    [["award_date", "recipient_name", "awarding_agency", "total_value_usd",
      "primary_capability_domain", "capability_maturity_stage",
      "threat_relevance_score", "description_raw_text"]],
    width="stretch", hide_index=True, height=380,
    column_config={
        "award_date": st.column_config.DateColumn("date"),
        "total_value_usd": st.column_config.NumberColumn(
            "value", format="compact"),
        "threat_relevance_score": st.column_config.ProgressColumn(
            "relevance", min_value=0, max_value=1, format="%.2f"),
        "description_raw_text": st.column_config.TextColumn(
            "description", width="large"),
    })

# ----------------------------------------------------------- companies
st.subheader("Contractors")
if companies is None:
    st.caption("No company rollup (needs OpenSanctions file for the "
               "sanctions cross-reference).")
else:
    sanctioned = companies[companies["opensanctions_match"].fillna(False)]
    if len(sanctioned):
        st.error("⚠️ OpenSanctions matches among contract recipients: "
                 + ", ".join(sanctioned["company_name"].tolist()))
    st.dataframe(
        companies.sort_values("total_contract_value_usd", ascending=False)
        [["company_name", "country_of_incorporation", "contract_count",
          "total_contract_value_usd", "primary_capability_domain",
          "opensanctions_match"]],
        width="stretch", hide_index=True,
        column_config={
            "total_contract_value_usd": st.column_config.NumberColumn(
                "total value", format="compact"),
            "opensanctions_match": st.column_config.CheckboxColumn(
                "sanctioned?"),
        })
