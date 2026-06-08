"""GPU Analytics — per-device detail + live utilization/memory/temp/power charts."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils import ui, charts
from utils.format import bytes_h, pct

store = ui.page_setup("GPU Analytics", "🎮")
opts = ui.sidebar(store)
snap = store.latest()
window = store.window(opts["range_seconds"])

ui.header("🎮 GPU Analytics", "Per-device GPU metrics")
ui.alert_banner(snap)

gpu = snap.get("gpu", {})
gpus = gpu.get("gpus", [])
if not gpus:
    st.warning("No GPUs detected. Ensure the NVIDIA driver / NVML is available "
               "(`nvidia-smi` works) on this host.")
    st.stop()

sel = opts["gpu_index"]
shown = gpus if sel is None else [g for g in gpus if g.get("index") == sel]


def gpu_in(snapshot, idx):
    for g in snapshot.get("gpu", {}).get("gpus", []):
        if g.get("index") == idx:
            return g
    return {}


times = ui.time_axis(window)

for g in shown:
    idx = g.get("index")
    st.subheader(f"GPU {idx} — {g.get('name', 'GPU')}")

    m = st.columns(5)
    m[0].metric("Utilization", pct(g.get("util", 0)))
    m[1].metric("Memory Used", bytes_h(g.get("mem_used", 0)))
    m[2].metric("Memory Free", bytes_h(g.get("mem_free", 0)))
    m[3].metric("Memory Total", bytes_h(g.get("mem_total", 0)))
    m[4].metric("Mem Utilization", pct(g.get("mem_util", 0)))

    m = st.columns(5)
    m[0].metric("Temperature", f"{g.get('temp', 0):.0f} °C")
    m[1].metric("Power Draw", f"{g.get('power', 0):.0f} W")
    m[2].metric("Power Limit", f"{g.get('power_limit', 0):.0f} W")
    m[3].metric("SM Clock", f"{g.get('clock_sm', 0):.0f} MHz")
    m[4].metric("Mem Clock", f"{g.get('clock_mem', 0):.0f} MHz")

    # Per-GPU live charts.
    uts = [gpu_in(s, idx).get("util", 0) for s in window]
    mus = [gpu_in(s, idx).get("mem_util", 0) for s in window]
    tps = [gpu_in(s, idx).get("temp", 0) for s in window]
    pws = [gpu_in(s, idx).get("power", 0) for s in window]

    a, b = st.columns(2)
    a.plotly_chart(charts.line(times, {f"GPU{idx} Util %": uts},
                   "GPU Utilization", "%", fill=True, ymax=100),
                   use_container_width=True)
    b.plotly_chart(charts.line(times, {f"GPU{idx} Mem %": mus},
                   "GPU Memory Utilization", "%", fill=True, ymax=100),
                   use_container_width=True)
    a, b = st.columns(2)
    a.plotly_chart(charts.line(times, {f"GPU{idx} Temp": tps},
                   "Temperature", "°C", fill=True),
                   use_container_width=True)
    b.plotly_chart(charts.line(times, {f"GPU{idx} Power": pws},
                   "Power Usage", "W", fill=True),
                   use_container_width=True)

    procs = g.get("processes", [])
    st.markdown(f"**Active Processes ({len(procs)})**")
    if procs:
        df = pd.DataFrame(procs)
        df["mem"] = df["mem"].map(lambda x: bytes_h(x))
        df = df.rename(columns={"pid": "PID", "name": "Process", "mem": "GPU Memory"})
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("No compute processes currently running on this GPU.")
    st.divider()

# --- Cross-GPU comparison -------------------------------------------------
if len(gpus) > 1 and sel is None:
    st.subheader("All GPUs — comparison")
    a, b = st.columns(2)
    a.plotly_chart(charts.bars(
        [f"GPU{g.get('index')}" for g in gpus],
        [g.get("util", 0) for g in gpus],
        "Utilization by GPU", "%"), use_container_width=True)
    b.plotly_chart(charts.bars(
        [f"GPU{g.get('index')}" for g in gpus],
        [g.get("temp", 0) for g in gpus],
        "Temperature by GPU", "°C", color=charts.ORANGE), use_container_width=True)
