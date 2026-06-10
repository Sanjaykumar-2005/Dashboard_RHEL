"""Disk Analytics — usage, read/write throughput, IOPS + live trends."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils import ui, charts, config
from utils.format import bytes_h, num_h, pct


@st.cache_data(ttl=300, show_spinner="Scanning folders…")
def _scan_dirs(root, threshold, depth):
    """Cached filesystem scan — never runs in the 1 s loop (du can be slow)."""
    from collectors import disk_usage
    return disk_usage.scan(root, threshold, depth)


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

# --- Large folders -----------------------------------------------------------
# Directories occupying more than the configured threshold (default 10 GB).
# Scanning the filesystem is slow, so it is cached (5 min) + a manual rescan
# button; it does NOT run on every 1 s refresh.
st.divider()
hdr, btn = st.columns([4, 1])
hdr.subheader(f"📁 Folders over {config.DISK_SCAN_THRESHOLD_GB:.0f} GB")
btn.button("🔄 Rescan", on_click=_scan_dirs.clear, use_container_width=True)
st.caption(f"Scanning `{config.DISK_SCAN_ROOT}` (depth {config.DISK_SCAN_DEPTH}) "
           "· cached 5 min")

scan = _scan_dirs(config.DISK_SCAN_ROOT, config.DISK_SCAN_THRESHOLD_BYTES,
                  config.DISK_SCAN_DEPTH)
if not scan.get("available"):
    st.warning(f"Folder scan failed: {scan.get('error') or 'unknown error'}")
elif not scan.get("dirs"):
    st.info(f"No folders above {config.DISK_SCAN_THRESHOLD_GB:.0f} GB under "
            f"`{config.DISK_SCAN_ROOT}`.")
else:
    dirs = scan["dirs"]
    df = pd.DataFrame(dirs)
    df["Size"] = df["bytes"].map(bytes_h)
    table = df.rename(columns={"path": "Folder"})[["Folder", "Size"]]
    a, b = st.columns([1, 1])
    with a:
        st.dataframe(table, use_container_width=True, hide_index=True, height=360)
    with b:
        top = dirs[:15]
        st.plotly_chart(charts.bars(
            [d["path"] for d in top][::-1],
            [d["bytes"] / (1024 ** 3) for d in top][::-1],
            "Largest folders (GB)", "GB"),
            use_container_width=True)
