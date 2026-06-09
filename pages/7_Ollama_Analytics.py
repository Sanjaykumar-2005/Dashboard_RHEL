"""Ollama Analytics — running models, memory footprint, throughput."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils import ui, charts, config
from utils.format import bytes_h, num_h

store = ui.page_setup("Ollama Analytics", "🦙")
opts = ui.sidebar(store)
snap = store.latest()
window = store.window(opts["range_seconds"])

ui.header("🦙 Ollama Analytics", f"Source: {config.OLLAMA_URL}")
ui.alert_banner(snap)

# Request volume from the systemd journal — independent of the /api endpoint.
ui.request_volume(snap, window, "ollama", "Request Volume (Ollama)")
st.divider()

o = snap.get("ollama", {})
if not o.get("available"):
    st.warning(f"Ollama API not reachable at `{config.OLLAMA_URL}`. "
               "Running-model details below need the API; the request-volume tiles "
               "above come from the journal and keep working regardless.")
    st.stop()

m = st.columns(4)
m[0].metric("Running Models", o.get("model_count", 0))
m[1].metric("Active Requests", o.get("active_requests", 0))
m[2].metric("Tokens/sec", num_h(o.get("tokens_per_sec", 0)))
m[3].metric("VRAM Used", bytes_h(o.get("vram_used", 0)))
st.divider()

rows = o.get("running_models", [])
if rows:
    df = pd.DataFrame(rows)
    df["size"] = df["size"].map(bytes_h)
    df["size_vram"] = df["size_vram"].map(bytes_h)
    df = df.rename(columns={"name": "Model", "size": "Size",
                            "size_vram": "VRAM", "expires_at": "Expires"})
    st.subheader("Running Models")
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No models currently loaded in Ollama.")

times = ui.time_axis(window)
a, b = st.columns(2)
with a:
    st.plotly_chart(charts.line(
        times, {"Running Models": [s["ollama"].get("model_count", 0) for s in window]},
        "Loaded Models", "count", fill=True),
        use_container_width=True)
with b:
    st.plotly_chart(charts.line(
        times, {"VRAM": [s["ollama"].get("vram_used", 0) for s in window]},
        "VRAM Usage (bytes)", "bytes", fill=True),
        use_container_width=True)
