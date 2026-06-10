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
    # Remember which page we're on so the sidebar nav dropdown can reflect it.
    st.session_state["_page"] = title
    # 1-second auto refresh (the spec's core requirement).
    st_autorefresh(interval=config.REFRESH_MS, key=f"refresh_{title}")
    return get_store()


def _nav():
    """Single 'Analytics' dropdown that replaces the native multipage list.

    Each page records its label via :func:`page_setup`; selecting a different
    one navigates there with ``st.switch_page``.
    """
    current = st.session_state.get("_page", config.PAGES[0][0])
    labels = [p[0] for p in config.PAGES]
    index = labels.index(current) if current in labels else 0
    # Key is per-page so the default index always applies cleanly on each page.
    choice = st.sidebar.selectbox("📂 Analytics", labels, index=index,
                                  key=f"nav_{current}")
    if choice != current:
        st.switch_page(dict(config.PAGES)[choice])


def _pill(label: str, on: bool) -> str:
    cls = "pill pill-on" if on else "pill pill-off"
    state = "online" if on else "offline"
    return f'<span class="{cls}">{label}: {state}</span>'


def _llm_online(snap: dict, key: str) -> bool:
    """Whether a serving source (vLLM/Ollama) is up.

    This deployment has no HTTP ``/metrics`` route, so the scrape-based
    ``available`` flag is always False.  We treat the source as online when the
    systemd-journal extraction it actually relies on is working
    (``snap["requests"][key]["available"]``), falling back to the HTTP flag for
    hosts that *do* expose the endpoint.
    """
    if snap.get(key, {}).get("available"):
        return True
    return bool(snap.get("requests", {}).get(key, {}).get("available"))


def sidebar(store) -> dict:
    snap = store.latest()
    gpu = snap.get("gpu", {})
    gpu_count = gpu.get("count", 0)

    st.sidebar.markdown(f"## ⚡ {config.APP_TITLE}")
    st.sidebar.caption("Live · no data persisted")

    # Single navigation dropdown (replaces the native page list).
    _nav()
    st.sidebar.divider()

    # Source status pills.
    st.sidebar.markdown(
        _pill("GPU", gpu.get("available", False)) + " " +
        _pill("vLLM", _llm_online(snap, "vllm")),
        unsafe_allow_html=True)
    st.sidebar.markdown(
        _pill("Ollama", _llm_online(snap, "ollama")),
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


def request_volume(snap: dict, window: list[dict], source_key: str,
                   label: str = "Request Volume"):
    """Render req/sec · /min · /hour · /day tiles + a trend, from journal counts.

    Always safe to call even when the source's /metrics endpoint is down — the
    numbers come from the systemd journal (``collectors/journal.py``), not the
    HTTP endpoint.  ``source_key`` is "vllm" or "ollama".
    """
    from utils import charts

    rq = snap.get("requests", {}).get(source_key, {})
    st.subheader(f"📊 {label}")
    if rq.get("error"):
        st.caption(f"⚠ journal unavailable: {rq['error']}")
    elif not rq.get("available"):
        st.caption("Waiting for the systemd journal… (set VLLM_UNITS / "
                   "OLLAMA_UNITS if the unit name differs)")
    else:
        st.caption(f"Counted live from journal units: "
                   f"`{', '.join(rq.get('units', [])) or '—'}`")

    c = st.columns(4)
    c[0].metric("Requests / sec", f"{rq.get('req_per_sec', 0):.2f}")
    c[1].metric("Requests / min", f"{int(rq.get('req_per_min', 0)):,}")
    c[2].metric("Requests / hour", f"{int(rq.get('req_per_hour', 0)):,}")
    c[3].metric("Requests today", f"{int(rq.get('req_per_day', 0)):,}",
                help="Total since local midnight (12 AM); resets daily.")

    if window:
        series = [s.get("requests", {}).get(source_key, {}).get("req_per_min", 0)
                  for s in window]
        st.plotly_chart(
            charts.line(time_axis(window), {"Req/min": series},
                        "Requests per minute (trailing-60s count)", "req/min",
                        fill=True),
            use_container_width=True)


@st.cache_data(ttl=3, show_spinner=False)
def _tail_journal(units_key: tuple, lines: int) -> dict:
    """Cached journalctl tail (ttl 3 s) so the 1 s refresh doesn't spam it."""
    from collectors import journal
    return journal.tail(list(units_key), lines)


def service_logs(units: list[str], label: str = "Service logs",
                 lines: int = 60):
    """Render the last ``lines`` systemd-journal lines for ``units``.

    Reuses the same unit names the request counters use (from
    ``journal_sources.json`` / env), so no service name is hardcoded here.
    """
    st.subheader(f"📝 {label}")
    if not units:
        st.caption("No units configured.")
        return
    res = _tail_journal(tuple(units), lines)
    st.caption(f"`journalctl -u {' -u '.join(units)} -n {lines}`")
    if not res.get("available"):
        st.caption(f"⚠ logs unavailable: {res.get('error') or '—'}")
        return
    body = "\n".join(res.get("lines", [])) or "(no recent log lines)"
    st.code(body, language="log")


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
