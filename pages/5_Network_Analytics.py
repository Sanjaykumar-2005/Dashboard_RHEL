"""Network Analytics — RX/TX throughput, packet rates, active connections."""
from __future__ import annotations

import streamlit as st

from utils import ui, charts
from utils.format import bytes_h, num_h

store = ui.page_setup("Network Analytics", "🌐")
opts = ui.sidebar(store)
snap = store.latest()
window = store.window(opts["range_seconds"])

ui.header("🌐 Network Analytics", "Interface throughput & connections")
ui.alert_banner(snap)

net = snap.get("network", {})
if not net.get("available"):
    st.warning("Network metrics unavailable.")
    st.stop()

m = st.columns(5)
m[0].metric("RX Bytes/sec", bytes_h(net.get("rx_bps", 0), unit_per_sec=True))
m[1].metric("TX Bytes/sec", bytes_h(net.get("tx_bps", 0), unit_per_sec=True))
m[2].metric("RX Packets/sec", num_h(net.get("rx_pps", 0)))
m[3].metric("TX Packets/sec", num_h(net.get("tx_pps", 0)))
m[4].metric("Active Connections", net.get("connections", 0))
st.divider()

times = ui.time_axis(window)
a, b = st.columns(2)
with a:
    st.plotly_chart(charts.line(
        times,
        {
            "RX": [s["network"].get("rx_bps", 0) for s in window],
            "TX": [s["network"].get("tx_bps", 0) for s in window],
        },
        "Throughput (bytes/s)", "B/s"),
        use_container_width=True)
with b:
    st.plotly_chart(charts.line(
        times,
        {
            "RX pkts": [s["network"].get("rx_pps", 0) for s in window],
            "TX pkts": [s["network"].get("tx_pps", 0) for s in window],
        },
        "Packets / second", "pkt/s"),
        use_container_width=True)

st.plotly_chart(charts.line(
    times, {"Connections": [s["network"].get("connections", 0) for s in window]},
    "Active Connections", "count", fill=True),
    use_container_width=True)
