"""Memory Analytics — RAM usage breakdown + live trends."""
from __future__ import annotations

import streamlit as st

from utils import ui, charts
from utils.format import bytes_h, pct

store = ui.page_setup("Memory Analytics", "💾")
opts = ui.sidebar(store)
snap = store.latest()
window = store.window(opts["range_seconds"])

ui.header("💾 Memory Analytics", "System RAM & swap")
ui.alert_banner(snap)

mem = snap.get("memory", {})
if not mem.get("available"):
    st.warning("Memory metrics unavailable.")
    st.stop()

m = st.columns(4)
m[0].metric("Total RAM", bytes_h(mem.get("total", 0)))
m[1].metric("Used RAM", bytes_h(mem.get("used", 0)), pct(mem.get("percent", 0)))
m[2].metric("Free RAM", bytes_h(mem.get("free", 0)))
m[3].metric("Cached", bytes_h(mem.get("cached", 0)))

m = st.columns(4)
m[0].metric("Buffers", bytes_h(mem.get("buffers", 0)))
m[1].metric("Swap Total", bytes_h(mem.get("swap_total", 0)))
m[2].metric("Swap Used", bytes_h(mem.get("swap_used", 0)))
m[3].metric("Swap %", pct(mem.get("swap_percent", 0)))
st.divider()

times = ui.time_axis(window)
a, b = st.columns(2)
with a:
    st.plotly_chart(charts.line(
        times, {"RAM %": [s["memory"].get("percent", 0) for s in window]},
        "RAM Utilization Trend", "%", fill=True, ymax=100),
        use_container_width=True)
with b:
    st.plotly_chart(charts.line(
        times,
        {
            "Used": [s["memory"].get("used", 0) for s in window],
            "Cached": [s["memory"].get("cached", 0) for s in window],
            "Free": [s["memory"].get("free", 0) for s in window],
        },
        "Memory Breakdown (bytes)", "bytes"),
        use_container_width=True)

# Composition snapshot.
st.subheader("Current Composition")
used = mem.get("used", 0)
cached = mem.get("cached", 0)
free = mem.get("free", 0)
st.plotly_chart(charts.bars(
    ["Used", "Cached", "Free"], [used, cached, free],
    "RAM Composition (bytes)", "bytes"), use_container_width=True)
