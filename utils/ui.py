"""Shared Streamlit UI scaffolding: page config, dark CSS, sidebar, auto-refresh.

Every page calls :func:`page_setup` first, then :func:`sidebar` to get the user's
GPU + time-range selection, then renders using the returned store/window.
"""
from __future__ import annotations

from datetime import datetime

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from utils import config
from utils.store import get_store

_CSS = """
<style>
  .stApp { background-color: #0e1117; }
  section[data-testid="stSidebar"] { background-color: #11151d; }
  div[data-testid="stMetric"] {
      background: #161a23; border: 1px solid #232838; border-radius: 10px;
      padding: 12px 14px;
  }
  div[data-testid="stMetricValue"] { font-size: 1.5rem; color: #76b900; }
  div[data-testid="stMetricLabel"] { color: #aab0bd; }
  h1, h2, h3 { color: #e6e6e6 !important; }
  .alert-crit {
      background: #3a1414; border: 1px solid #ff4b4b; color: #ff6b6b;
      padding: 10px 14px; border-radius: 8px; margin-bottom: 8px;
      font-weight: 600;
  }
  .alert-ok {
      background: #14210f; border: 1px solid #2f6b1f; color: #7bd05a;
      padding: 10px 14px; border-radius: 8px; margin-bottom: 8px;
  }
  .pill { display:inline-block; padding:2px 10px; border-radius:12px;
          font-size:0.75rem; font-weight:600; }
  .pill-on  { background:#16331a; color:#76b900; border:1px solid #2f6b1f; }
  .pill-off { background:#2a2230; color:#9aa0ad; border:1px solid #3a3340; }
</style>
"""


def page_setup(title: str, icon: str = "📊"):
    """Configure the page, inject CSS, start auto-refresh, return the store."""
    st.set_page_config(page_title=f"{config.APP_TITLE} · {title}",
                       page_icon=icon, layout="wide",
                       initial_sidebar_state="expanded")
    st.markdown(_CSS, unsafe_allow_html=True)
    # 1-second auto refresh (the spec's core requirement).
    st_autorefresh(interval=config.REFRESH_MS, key=f"refresh_{title}")
    return get_store()


def _pill(label: str, on: bool) -> str:
    cls = "pill pill-on" if on else "pill pill-off"
    state = "online" if on else "offline"
    return f'<span class="{cls}">{label}: {state}</span>'


def sidebar(store) -> dict:
    snap = store.latest()
    gpu = snap.get("gpu", {})
    gpu_count = gpu.get("count", 0)

    st.sidebar.markdown(f"## ⚡ {config.APP_TITLE}")
    st.sidebar.caption("Live · no data persisted")

    # Source status pills.
    st.sidebar.markdown(
        _pill("GPU", gpu.get("available", False)) + " " +
        _pill("vLLM", snap.get("vllm", {}).get("available", False)),
        unsafe_allow_html=True)
    st.sidebar.markdown(
        _pill("Ollama", snap.get("ollama", {}).get("available", False)) + " " +
        _pill("Logs", snap.get("logs", {}).get("available", False)),
        unsafe_allow_html=True)
    st.sidebar.divider()

    # GPU selector.
    if gpu_count > 0:
        options = ["All GPUs"] + [
            f"GPU {g.get('index')} — {g.get('name', 'GPU')}" for g in gpu.get("gpus", [])
        ]
    else:
        options = ["All GPUs"]
    choice = st.sidebar.selectbox("GPU Selector", options, key="gpu_sel")
    gpu_index = None if choice == "All GPUs" else options.index(choice) - 1

    # Time-range selector.
    range_label = st.sidebar.selectbox(
        "Time Range", list(config.TIME_RANGES.keys()), index=1, key="range_sel")
    range_seconds = config.TIME_RANGES[range_label]

    st.sidebar.divider()
    ts = snap.get("ts")
    if ts:
        st.sidebar.caption(f"Last sample: {datetime.fromtimestamp(ts):%H:%M:%S}")
    st.sidebar.caption(f"Refresh: {config.REFRESH_MS} ms · "
                       f"history: {config.HISTORY_LEN}s")
    if store.errors:
        with st.sidebar.expander("⚠ Collector errors"):
            for k, v in store.errors.items():
                st.caption(f"**{k}**: {v}")

    return {"gpu_index": gpu_index, "range_seconds": range_seconds,
            "range_label": range_label}


def header(title: str, subtitle: str = ""):
    st.markdown(f"# {title}")
    if subtitle:
        st.caption(subtitle)


def time_axis(window: list[dict]) -> list[datetime]:
    return [datetime.fromtimestamp(s["ts"]) for s in window]


def alert_banner(snap: dict):
    """Render a compact alert strip; returns the active alert list."""
    from utils import alerts as alerts_mod
    active = alerts_mod.evaluate(snap)
    if active:
        msgs = " &nbsp;|&nbsp; ".join(a["message"] for a in active[:4])
        more = f" (+{len(active) - 4} more)" if len(active) > 4 else ""
        st.markdown(f'<div class="alert-crit">🚨 {len(active)} active alert(s): '
                    f'{msgs}{more}</div>', unsafe_allow_html=True)
    return active
