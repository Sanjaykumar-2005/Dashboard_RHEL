"""Threshold-based alert evaluation against the latest snapshot."""
from __future__ import annotations

from utils import config

T = config.THRESHOLDS


def evaluate(snap: dict) -> list[dict]:
    """Return a list of active alerts, each: {level, source, metric, value, message}."""
    alerts: list[dict] = []

    def add(source, metric, value, limit, fmt):
        alerts.append({
            "level": "critical",
            "source": source,
            "metric": metric,
            "value": value,
            "limit": limit,
            "message": fmt,
        })

    # --- GPU (per device) ---
    gpu = snap.get("gpu", {})
    for g in gpu.get("gpus", []):
        idx = g.get("index", "?")
        if g.get("util", 0) > T["gpu_util"]:
            add(f"GPU{idx}", "Utilization", g["util"], T["gpu_util"],
                f"GPU{idx} utilization {g['util']:.0f}% > {T['gpu_util']:.0f}%")
        if g.get("mem_util", 0) > T["gpu_mem"]:
            add(f"GPU{idx}", "Memory", g["mem_util"], T["gpu_mem"],
                f"GPU{idx} memory {g['mem_util']:.0f}% > {T['gpu_mem']:.0f}%")
        if g.get("temp", 0) > T["gpu_temp"]:
            add(f"GPU{idx}", "Temperature", g["temp"], T["gpu_temp"],
                f"GPU{idx} temperature {g['temp']:.0f}°C > {T['gpu_temp']:.0f}°C")

    # --- CPU ---
    cpu = snap.get("cpu", {})
    if cpu.get("percent", 0) > T["cpu"]:
        add("CPU", "Usage", cpu["percent"], T["cpu"],
            f"CPU usage {cpu['percent']:.0f}% > {T['cpu']:.0f}%")

    # --- Disk ---
    disk = snap.get("disk", {})
    if disk.get("percent", 0) > T["disk"]:
        add("Disk", "Usage", disk["percent"], T["disk"],
            f"Disk usage {disk['percent']:.0f}% > {T['disk']:.0f}%")

    # --- LLM serving ---
    llm = snap.get("llm", {})
    if llm.get("queue", 0) > T["queue"]:
        add("LLM", "Queue", llm["queue"], T["queue"],
            f"Queue length {llm['queue']} > {T['queue']}")
    if llm.get("ttft", 0) > T["ttft"]:
        add("LLM", "TTFT", llm["ttft"], T["ttft"],
            f"TTFT {llm['ttft']:.2f}s > {T['ttft']:.1f}s")

    return alerts
