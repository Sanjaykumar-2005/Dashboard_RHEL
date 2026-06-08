"""Alerts Dashboard — live threshold breaches shown in red."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils import ui, config

store = ui.page_setup("Alerts", "🚨")
opts = ui.sidebar(store)
snap = store.latest()

from utils import alerts as alerts_mod  # noqa: E402

active = alerts_mod.evaluate(snap)

ui.header("🚨 Alerts Dashboard", "Real-time threshold monitoring")

c = st.columns(3)
c[0].metric("Active Alerts", len(active))
c[1].metric("Sources Monitored", "GPU · CPU · Disk · LLM")
c[2].metric("Status", "DEGRADED" if active else "HEALTHY")

st.divider()

if active:
    for a in active:
        st.markdown(
            f'<div class="alert-crit">🚨 <b>{a["source"]} · {a["metric"]}</b> — '
            f'{a["message"]}</div>',
            unsafe_allow_html=True)
    df = pd.DataFrame(active)[["level", "source", "metric", "value", "limit", "message"]]
    df = df.rename(columns={"level": "Level", "source": "Source", "metric": "Metric",
                            "value": "Value", "limit": "Limit", "message": "Detail"})
    df["Value"] = df["Value"].map(lambda x: f"{float(x):.1f}")
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.markdown('<div class="alert-ok">✅ All systems within thresholds. '
                'No active alerts.</div>', unsafe_allow_html=True)

st.divider()
st.subheader("Alert Thresholds")
T = config.THRESHOLDS
rules = pd.DataFrame([
    {"Rule": "GPU Utilization", "Trigger": f"> {T['gpu_util']:.0f} %"},
    {"Rule": "GPU Memory", "Trigger": f"> {T['gpu_mem']:.0f} %"},
    {"Rule": "GPU Temperature", "Trigger": f"> {T['gpu_temp']:.0f} °C"},
    {"Rule": "CPU Usage", "Trigger": f"> {T['cpu']:.0f} %"},
    {"Rule": "Disk Usage", "Trigger": f"> {T['disk']:.0f} %"},
    {"Rule": "Queue Length", "Trigger": f"> {T['queue']}"},
    {"Rule": "TTFT", "Trigger": f"> {T['ttft']:.1f} s"},
])
st.dataframe(rules, use_container_width=True, hide_index=True)
