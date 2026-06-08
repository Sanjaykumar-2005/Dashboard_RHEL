"""Disk Analytics — usage, read/write throughput, IOPS + live trends."""
from __future__ import annotations

import streamlit as st

from utils import ui, charts
from utils.format import bytes_h, num_h, pct

store = ui.page_setup("Disk Analytics", "🗄️")
opts = ui.sidebar(store)
snap = store.latest()
window = store.window(opts["range_seconds"])

ui.header("🗄️ Disk Analytics", "Storage utilization & I/O")
ui.alert_banner(snap)

disk = snap.get("disk", {})
if not disk.get("available"):
    st.warning("Disk metrics unavailable.")
    st.stop()

m = st.columns(5)
m[0].metric("Disk Usage", pct(disk.get("percent", 0)))
m[1].metric("Used", bytes_h(disk.get("used", 0)))
m[2].metric("Free", bytes_h(disk.get("free", 0)))
m[3].metric("Read Speed", bytes_h(disk.get("read_bps", 0), unit_per_sec=True))
m[4].metric("Write Speed", bytes_h(disk.get("write_bps", 0), unit_per_sec=True))

m = st.columns(5)
m[0].metric("IOPS", num_h(disk.get("iops", 0)))
m[1].metric("Read IOPS", num_h(disk.get("read_iops", 0)))
m[2].metric("Write IOPS", num_h(disk.get("write_iops", 0)))
m[3].metric("Total", bytes_h(disk.get("total", 0)))
st.divider()

times = ui.time_axis(window)
a, b = st.columns(2)
with a:
    st.plotly_chart(charts.line(
        times,
        {
            "Read": [s["disk"].get("read_bps", 0) for s in window],
            "Write": [s["disk"].get("write_bps", 0) for s in window],
        },
        "Disk Throughput (bytes/s)", "B/s"),
        use_container_width=True)
with b:
    st.plotly_chart(charts.line(
        times,
        {
            "Read IOPS": [s["disk"].get("read_iops", 0) for s in window],
            "Write IOPS": [s["disk"].get("write_iops", 0) for s in window],
        },
        "IOPS", "ops/s"),
        use_container_width=True)

st.plotly_chart(charts.line(
    times, {"Disk Usage %": [s["disk"].get("percent", 0) for s in window]},
    "Disk Usage Trend", "%", fill=True, ymax=100),
    use_container_width=True)
