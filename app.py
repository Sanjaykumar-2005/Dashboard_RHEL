"""
Server Monitor — Overview Dashboard (multipage entry point).

Run with:  streamlit run app.py
All other pages live in ./pages and share the same in-memory store.
"""
from __future__ import annotations

import streamlit as st

from utils import ui
from utils.format import bytes_h, num_h, pct
from utils import charts

cfg = ui.page_setup("Overview", "🖥️")
store = ui.get_store()
opts = ui.sidebar(store)

snap = store.latest()
window = store.window(opts["range_seconds"])

ui.header("🖥️ Overview Dashboard", "Live cluster-wide health · refreshes every second")
ui.alert_banner(snap)

gpu = snap.get("gpu", {})
cpu = snap.get("cpu", {})
mem = snap.get("memory", {})
disk = snap.get("disk", {})
net = snap.get("network", {})
llm = snap.get("llm", {})
vllm = snap.get("vllm", {})

# --- Row 1: GPU + system headline metrics --------------------------------
c = st.columns(6)
c[0].metric("Total GPUs", gpu.get("count", 0))
c[1].metric("Active GPUs", gpu.get("active", 0))
c[2].metric("Avg GPU Util", pct(gpu.get("avg_util", 0)))
c[3].metric("Avg GPU Mem", pct(gpu.get("avg_mem_util", 0)))
c[4].metric("CPU Usage", pct(cpu.get("percent", 0)))
c[5].metric("RAM Usage", pct(mem.get("percent", 0)))

c = st.columns(6)
c[0].metric("Disk Usage", pct(disk.get("percent", 0)))
c[1].metric("Net RX", bytes_h(net.get("rx_bps", 0), unit_per_sec=True))
c[2].metric("Net TX", bytes_h(net.get("tx_bps", 0), unit_per_sec=True))
c[3].metric("Active Models", llm.get("active_models", 0))
c[4].metric("Queue Length", llm.get("queue", 0))
c[5].metric("Requests/sec", num_h(llm.get("requests_per_sec", 0), 2))

c = st.columns(6)
c[0].metric("Tokens/sec", num_h(llm.get("tokens_per_sec", 0)))
c[1].metric("Concurrent Reqs", llm.get("concurrent_requests", 0))
c[2].metric("vLLM Running", vllm.get("running", 0))
c[3].metric("vLLM Pending", vllm.get("pending", 0))
c[4].metric("Total RAM", bytes_h(mem.get("total", 0)))
c[5].metric("Free RAM", bytes_h(mem.get("free", 0)))

st.divider()

# --- Trends ---------------------------------------------------------------
times = ui.time_axis(window)
g1, g2 = st.columns(2)
with g1:
    st.plotly_chart(charts.line(
        times,
        {
            "Avg GPU Util %": [s["gpu"].get("avg_util", 0) for s in window],
            "CPU %": [s["cpu"].get("percent", 0) for s in window],
            "RAM %": [s["memory"].get("percent", 0) for s in window],
        },
        "Compute Utilization", "%", ymax=100),
        use_container_width=True)
with g2:
    st.plotly_chart(charts.line(
        times,
        {
            "RX": [s["network"].get("rx_bps", 0) for s in window],
            "TX": [s["network"].get("tx_bps", 0) for s in window],
        },
        "Network Throughput (bytes/s)", "B/s"),
        use_container_width=True)

g3, g4 = st.columns(2)
with g3:
    st.plotly_chart(charts.line(
        times,
        {"Tokens/sec": [s["llm"].get("tokens_per_sec", 0) for s in window]},
        "LLM Tokens / second", "tok/s", fill=True),
        use_container_width=True)
with g4:
    st.plotly_chart(charts.line(
        times,
        {
            "Queue": [s["llm"].get("queue", 0) for s in window],
            "Concurrent": [s["llm"].get("concurrent_requests", 0) for s in window],
        },
        "Requests: Queue vs Concurrent", "count"),
        use_container_width=True)

st.caption("Use the sidebar to pick a GPU, change the time range, or jump to a "
           "detailed analytics page. No metrics are written to any database.")
