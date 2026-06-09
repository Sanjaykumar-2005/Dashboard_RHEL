"""vLLM Analytics — scraped from the vLLM Prometheus metrics endpoint."""
from __future__ import annotations

import streamlit as st

from utils import ui, charts, config
from utils.format import num_h, pct, secs

store = ui.page_setup("vLLM Analytics", "🚀")
opts = ui.sidebar(store)
snap = store.latest()
window = store.window(opts["range_seconds"])

ui.header("🚀 vLLM Analytics", f"Source: {config.VLLM_METRICS_URL}")
ui.alert_banner(snap)

# Request volume from the systemd journal — independent of the /metrics endpoint,
# so it stays live even when the Prometheus scrape below is unavailable.
ui.request_volume(snap, window, "vllm", "Request Volume (vLLM)")
st.divider()

v = snap.get("vllm", {})
if not v.get("available"):
    st.warning(f"vLLM metrics endpoint not reachable at `{config.VLLM_METRICS_URL}`. "
               "Token throughput / latency below need /metrics; the request-volume "
               "tiles above come from the journal and keep working regardless.")
    st.stop()

m = st.columns(5)
m[0].metric("Running Requests", v.get("running", 0))
m[1].metric("Pending Requests", v.get("pending", 0))
m[2].metric("Queue Length", v.get("queue", 0))
m[3].metric("Batch Size", v.get("batch_size", 0))
m[4].metric("Tokens/sec", num_h(v.get("tokens_per_sec", 0)))

m = st.columns(5)
m[0].metric("Prompt Tokens/sec", num_h(v.get("prompt_tokens_per_sec", 0)))
m[1].metric("GPU Cache Usage", pct(v.get("gpu_cache_usage", 0)))
m[2].metric("Avg TTFT", secs(v.get("ttft", 0)))
m[3].metric("Avg E2E Latency", secs(v.get("e2e_latency", 0)))
m[4].metric("Success/sec", num_h(v.get("success_per_sec", 0), 2))
st.divider()

times = ui.time_axis(window)
a, b = st.columns(2)
with a:
    st.plotly_chart(charts.line(
        times,
        {
            "Running": [s["vllm"].get("running", 0) for s in window],
            "Pending": [s["vllm"].get("pending", 0) for s in window],
        },
        "Requests: Running vs Pending", "count"),
        use_container_width=True)
with b:
    st.plotly_chart(charts.line(
        times,
        {
            "Generation": [s["vllm"].get("tokens_per_sec", 0) for s in window],
            "Prompt": [s["vllm"].get("prompt_tokens_per_sec", 0) for s in window],
        },
        "Token Throughput", "tok/s", fill=False),
        use_container_width=True)

a, b = st.columns(2)
with a:
    st.plotly_chart(charts.line(
        times, {"Queue": [s["vllm"].get("queue", 0) for s in window]},
        "Queue Length", "count", fill=True),
        use_container_width=True)
with b:
    st.plotly_chart(charts.line(
        times, {"GPU Cache %": [s["vllm"].get("gpu_cache_usage", 0) for s in window]},
        "KV-Cache Usage", "%", fill=True, ymax=100),
        use_container_width=True)
