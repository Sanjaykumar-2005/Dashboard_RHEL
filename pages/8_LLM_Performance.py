"""LLM Performance Dashboard — combined serving KPIs + latency percentiles.

P95/P99 are computed over the rolling in-memory history of latency samples
(no per-request store / DB), giving a live approximation of the tail.
"""
from __future__ import annotations

import numpy as np
import streamlit as st

from utils import ui, charts
from utils.format import num_h, secs

store = ui.page_setup("LLM Performance", "📈")
opts = ui.sidebar(store)
snap = store.latest()
window = store.window(opts["range_seconds"])

ui.header("📈 LLM Performance Dashboard", "End-to-end serving KPIs (vLLM + Ollama)")
ui.alert_banner(snap)

llm = snap.get("llm", {})

# Latency tail from the history window.
lat_samples = [s["llm"].get("avg_latency", 0) for s in window if s["llm"].get("avg_latency", 0) > 0]
ttft_samples = [s["llm"].get("ttft", 0) for s in window if s["llm"].get("ttft", 0) > 0]
p95 = float(np.percentile(lat_samples, 95)) if lat_samples else 0.0
p99 = float(np.percentile(lat_samples, 99)) if lat_samples else 0.0

m = st.columns(5)
m[0].metric("Requests/sec", num_h(llm.get("requests_per_sec", 0), 2))
m[1].metric("Concurrent Users", llm.get("concurrent_users", 0))
m[2].metric("Concurrent Requests", llm.get("concurrent_requests", 0))
m[3].metric("Queue Length", llm.get("queue", 0))
m[4].metric("Tokens/sec", num_h(llm.get("tokens_per_sec", 0)))

m = st.columns(5)
m[0].metric("TTFT", secs(llm.get("ttft", 0)))
m[1].metric("Avg Latency", secs(llm.get("avg_latency", 0)))
m[2].metric("P95 Latency", secs(p95))
m[3].metric("P99 Latency", secs(p99))
m[4].metric("Active Models", llm.get("active_models", 0))
st.divider()

times = ui.time_axis(window)
a, b = st.columns(2)
with a:
    st.plotly_chart(charts.line(
        times,
        {
            "Avg": [s["llm"].get("avg_latency", 0) for s in window],
            "TTFT": [s["llm"].get("ttft", 0) for s in window],
        },
        "Latency (seconds)", "s"),
        use_container_width=True)
with b:
    st.plotly_chart(charts.line(
        times, {"Tokens/sec": [s["llm"].get("tokens_per_sec", 0) for s in window]},
        "Throughput", "tok/s", fill=True),
        use_container_width=True)

a, b = st.columns(2)
with a:
    st.plotly_chart(charts.line(
        times,
        {
            "Concurrent": [s["llm"].get("concurrent_requests", 0) for s in window],
            "Queue": [s["llm"].get("queue", 0) for s in window],
        },
        "Concurrency & Queue", "count"),
        use_container_width=True)
with b:
    st.plotly_chart(charts.line(
        times, {"Requests/sec": [s["llm"].get("requests_per_sec", 0) for s in window]},
        "Request Rate", "req/s", fill=True),
        use_container_width=True)

if not llm.get("available"):
    st.info("No LLM backend reporting yet — start vLLM and/or Ollama to populate "
            "these KPIs.")
