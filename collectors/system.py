"""CPU / memory / disk / network metrics via psutil.

Rate metrics (disk read/write, network rx/tx, IOPS, packets) are computed as the
delta between successive calls.  Because a single background thread drives the
sampling loop at ~1 s cadence, the deltas are effectively per-second rates.
"""
from __future__ import annotations

import os
import time

import psutil

# Previous counters for delta/rate computation.
_prev = {
    "disk": None,
    "net": None,
}


def collect_cpu() -> dict:
    per_core = psutil.cpu_percent(interval=None, percpu=True)
    overall = sum(per_core) / len(per_core) if per_core else 0.0
    try:
        load1, load5, load15 = psutil.getloadavg()
    except (AttributeError, OSError):
        load1 = load5 = load15 = 0.0
    try:
        freq = psutil.cpu_freq()
        cur_freq = freq.current if freq else 0.0
    except Exception:
        cur_freq = 0.0
    return {
        "available": True,
        "percent": overall,
        "per_core": per_core,
        "cores": len(per_core),
        "load1": load1, "load5": load5, "load15": load15,
        "freq": cur_freq,
        "processes": len(psutil.pids()),
    }


def collect_memory() -> dict:
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()
    return {
        "available": True,
        "total": float(vm.total),
        "used": float(vm.used),
        "free": float(vm.available),
        "cached": float(getattr(vm, "cached", 0) or 0),
        "buffers": float(getattr(vm, "buffers", 0) or 0),
        "percent": float(vm.percent),
        "swap_total": float(sw.total),
        "swap_used": float(sw.used),
        "swap_percent": float(sw.percent),
    }


def collect_disk() -> dict:
    root = os.path.abspath(os.sep)
    usage = psutil.disk_usage(root)
    io = psutil.disk_io_counters()
    dt = _elapsed_disk()

    read_bps = write_bps = read_iops = write_iops = 0.0
    if io is not None:
        prev = _prev["disk"]
        if prev is not None and dt > 0:
            read_bps = max(0.0, (io.read_bytes - prev.read_bytes) / dt)
            write_bps = max(0.0, (io.write_bytes - prev.write_bytes) / dt)
            read_iops = max(0.0, (io.read_count - prev.read_count) / dt)
            write_iops = max(0.0, (io.write_count - prev.write_count) / dt)
        _prev["disk"] = io

    return {
        "available": True,
        "total": float(usage.total),
        "used": float(usage.used),
        "free": float(usage.free),
        "percent": float(usage.percent),
        "read_bps": read_bps,
        "write_bps": write_bps,
        "read_iops": read_iops,
        "write_iops": write_iops,
        "iops": read_iops + write_iops,
    }


def collect_network() -> dict:
    io = psutil.net_io_counters()
    dt = _elapsed_net()
    rx_bps = tx_bps = rx_pps = tx_pps = 0.0
    prev = _prev["net"]
    if prev is not None and dt > 0:
        rx_bps = max(0.0, (io.bytes_recv - prev.bytes_recv) / dt)
        tx_bps = max(0.0, (io.bytes_sent - prev.bytes_sent) / dt)
        rx_pps = max(0.0, (io.packets_recv - prev.packets_recv) / dt)
        tx_pps = max(0.0, (io.packets_sent - prev.packets_sent) / dt)
    _prev["net"] = io

    try:
        conns = len(psutil.net_connections(kind="inet"))
    except Exception:
        conns = 0

    return {
        "available": True,
        "rx_bps": rx_bps, "tx_bps": tx_bps,
        "rx_pps": rx_pps, "tx_pps": tx_pps,
        "packets_ps": rx_pps + tx_pps,
        "connections": conns,
    }


# Separate timers so disk/net deltas stay independent and correct.
_dt_state = {"disk": None, "net": None}


def _elapsed_disk() -> float:
    now = time.time()
    prev = _dt_state["disk"]
    _dt_state["disk"] = now
    return (now - prev) if prev else 1.0


def _elapsed_net() -> float:
    now = time.time()
    prev = _dt_state["net"]
    _dt_state["net"] = now
    return (now - prev) if prev else 1.0


def collect() -> dict:
    return {
        "cpu": collect_cpu(),
        "memory": collect_memory(),
        "disk": collect_disk(),
        "network": collect_network(),
    }
