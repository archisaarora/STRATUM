"""Signal Tracking — the analyst workflow: triage the queue, annotate,
escalate or dismiss. State persists to analyst_state.json next to the data."""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import loaders  # noqa: E402

st.set_page_config(page_title="STRATUM — Signal Tracking", page_icon="🛰️",
                   layout="wide")
out_dir = loaders.sidebar()

signals = loaders.load_signals(out_dir)
names = loaders.country_names(out_dir)

st.title("THREAT SIGNAL MANAGEMENT")

if signals is None:
    st.info("No signals yet — run the pipeline.")
    st.stop()

q1, q2, q3, q4 = st.columns(4)
q1.metric("In queue (unreviewed)",
          int((~signals["reviewed"] & ~signals["dismissed"]).sum()))
q2.metric("Reviewed", int(signals["reviewed"].sum()))
q3.metric("Escalated", int(signals["escalated"].sum()))
q4.metric("Dismissed", int(signals["dismissed"].sum()))

# ----------------------------------------------------------- timeline
st.subheader("Signal timeline")
t = signals.copy()
t["window_end"] = t["window_end"].astype(str)
fig = px.scatter(
    t, x="window_end", y="country_code", size="signal_strength",
    color="signal_type", hover_data=["domain", "priority"],
    category_orders={"country_code": sorted(t["country_code"].unique())})
fig.update_layout(height=280, legend_title=None, **loaders.PLOTLY_LAYOUT)
st.plotly_chart(fig, width="stretch")

# ----------------------------------------------------------- queue
tab_queue, tab_done = st.tabs(["Review queue", "Reviewed / dismissed"])


def render_signal(r) -> None:
    flag = {"compound_signal": "🟣", "material_anomaly": "🔴",
            "procurement_acceleration": "🟠", "budget_discrepancy": "🟡",
            "arms_transfer_spike": "🔵"}.get(r.signal_type, "⚪")
    title = (f"{flag} {names.get(r.country_code, r.country_code)} · "
             f"{r.domain} · {r.signal_type} · priority {r.priority:.2f}")
    with st.expander(title):
        st.write(r.description_text)
        st.caption(f"strength {r.signal_strength:.2f} · confidence "
                   f"{r.confidence_score:.2f} · window {r.window_end} · "
                   f"evidence: {', '.join(r.supporting_evidence) or '—'}")
        notes = st.text_area("Analyst notes", value=r.analyst_notes,
                             key=f"notes_{r.signal_id}", height=80)
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("💾 Save notes", key=f"save_{r.signal_id}"):
            loaders.update_signal_state(out_dir, r.signal_id, notes=notes)
            st.toast("Notes saved")
            st.rerun()
        if not r.reviewed and c2.button("✅ Mark reviewed",
                                        key=f"rev_{r.signal_id}"):
            loaders.update_signal_state(out_dir, r.signal_id,
                                        reviewed=True, notes=notes)
            st.rerun()
        if not r.escalated and c3.button("🚨 Escalate",
                                         key=f"esc_{r.signal_id}"):
            loaders.update_signal_state(
                out_dir, r.signal_id, escalated=True, reviewed=True,
                notes=notes)
            st.rerun()
        if not r.dismissed and c4.button("🗑️ Dismiss",
                                         key=f"dis_{r.signal_id}"):
            loaders.update_signal_state(
                out_dir, r.signal_id, dismissed=True, reviewed=True,
                notes=notes)
            st.rerun()
        if r.escalated:
            st.error("ESCALATED — generate the report from the Country "
                     "Deep-Dive page and route per your workflow.")


with tab_queue:
    queue = signals[~signals["reviewed"] & ~signals["dismissed"]]
    if queue.empty:
        st.success("Queue clear — nothing unreviewed.")
    for r in queue.itertuples(index=False):
        render_signal(r)

with tab_done:
    done = signals[signals["reviewed"] | signals["dismissed"]]
    if done.empty:
        st.caption("Nothing reviewed yet.")
    for r in done.itertuples(index=False):
        render_signal(r)
