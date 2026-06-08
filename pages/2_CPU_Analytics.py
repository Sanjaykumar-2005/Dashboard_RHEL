"""CPU Analytics — overall + per-core usage, load average, core heatmap."""
from __future__ import annotations

import numpy as np
import streamlit as st

from utils import ui, charts
from utils.format import pct

store = ui.page_setup("CPU Analytics", "🧮")
opts = ui.sidebar(store)
snap = store.latest()
window = store.window(opts["range_seconds"])

ui.header("🧮 CPU Analytics", "Xeon processor utilization")
ui.alert_banner(snap)

cpu = snap.get("cpu", {})
if not cpu.get("available"):
    st.warning("CPU metrics unavailable.")
    st.stop()

m = st.columns(5)
m[0].metric("CPU Usage", pct(cpu.get("percent", 0)))
m[1].metric("Cores", cpu.get("cores", 0))
m[2].metric("Load (1m)", f"{cpu.get('load1', 0):.2f}")
m[3].metric("Load (5m)", f"{cpu.get('load5', 0):.2f}")
m[4].metric("Running Processes", cpu.get("processes", 0))

m = st.columns(5)
m[0].metric("Load (15m)", f"{cpu.get('load15', 0):.2f}")
m[1].metric("Frequency", f"{cpu.get('freq', 0):.0f} MHz")
st.divider()

times = ui.time_axis(window)

a, b = st.columns(2)
with a:
    st.plotly_chart(charts.line(
        times, {"CPU %": [s["cpu"].get("percent", 0) for s in window]},
        "CPU Utilization Trend", "%", fill=True, ymax=100),
        use_container_width=True)
with b:
    st.plotly_chart(charts.line(
        times,
        {
            "1m": [s["cpu"].get("load1", 0) for s in window],
            "5m": [s["cpu"].get("load5", 0) for s in window],
            "15m": [s["cpu"].get("load15", 0) for s in window],
        },
        "Load Average", "load"),
        use_container_width=True)

# Per-core bar (current) + heatmap (over time).
per_core = cpu.get("per_core", [])
st.subheader("Per-Core Usage")
st.plotly_chart(charts.bars(
    [f"C{i}" for i in range(len(per_core))], per_core,
    "Current Per-Core Utilization", "%"), use_container_width=True)

# Core heatmap: rows = cores, cols = time samples.
core_window = [s["cpu"].get("per_core", []) for s in window if s["cpu"].get("per_core")]
if core_window:
    ncores = max(len(c) for c in core_window)
    matrix = np.zeros((ncores, len(core_window)))
    for j, c in enumerate(core_window):
        for i in range(len(c)):
            matrix[i, j] = c[i]
    st.plotly_chart(charts.heatmap(
        matrix,
        x_labels=[f"{i}" for i in range(len(core_window))],
        y_labels=[f"Core {i}" for i in range(ncores)],
        title="Core Heatmap (utilization % over time)",
        height=max(280, ncores * 16)), use_container_width=True)
