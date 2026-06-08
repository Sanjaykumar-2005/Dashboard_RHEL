"""Request Analytics — live tail of the application request log."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils import ui, charts, config
from utils.format import num_h, secs

store = ui.page_setup("Request Analytics", "📜")
opts = ui.sidebar(store)
snap = store.latest()
window = store.window(opts["range_seconds"])

ui.header("📜 Request Analytics", f"Tailing: {config.REQUEST_LOG_PATH}")
ui.alert_banner(snap)

logs = snap.get("logs", {})
rows = logs.get("rows", [])

if not logs.get("available"):
    st.warning(f"Request log not found at `{config.REQUEST_LOG_PATH}`. "
               "Point REQUEST_LOG_PATH at your app's JSON-lines request log. "
               "Expected fields: ts, user, model, input_tokens, output_tokens, "
               "latency, status.")
if not rows:
    st.info("No request records yet.")
    st.stop()

# Summary over the recent rows.
recent = rows[-300:]
df = pd.DataFrame(recent)
total = len(df)
ok = int((df["status"] == "ok").sum()) if "status" in df else 0
avg_lat = float(pd.to_numeric(df.get("latency", 0), errors="coerce").mean() or 0)
in_tok = int(pd.to_numeric(df.get("input_tokens", 0), errors="coerce").sum() or 0)
out_tok = int(pd.to_numeric(df.get("output_tokens", 0), errors="coerce").sum() or 0)

m = st.columns(5)
m[0].metric("Records (recent)", total)
m[1].metric("Success", ok)
m[2].metric("Avg Latency", secs(avg_lat))
m[3].metric("Input Tokens", num_h(in_tok))
m[4].metric("Output Tokens", num_h(out_tok))
st.divider()

# Continuously updating table (newest first).
show = df.iloc[::-1].copy()
order = ["timestamp", "user", "model", "input_tokens", "output_tokens",
         "latency", "status"]
order = [c for c in order if c in show.columns]
show = show[order].rename(columns={
    "timestamp": "Timestamp", "user": "User", "model": "Model",
    "input_tokens": "Input Tok", "output_tokens": "Output Tok",
    "latency": "Latency (s)", "status": "Status"})
st.subheader("Live Request Stream")
st.dataframe(show, use_container_width=True, hide_index=True, height=420)

# Per-model volume.
if "model" in df.columns:
    counts = df["model"].value_counts()
    st.plotly_chart(charts.bars(
        list(counts.index), list(counts.values),
        "Requests by Model (recent window)", "count"),
        use_container_width=True)
