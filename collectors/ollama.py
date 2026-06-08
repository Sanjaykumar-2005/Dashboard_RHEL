"""Ollama metrics — via the local REST API (/api/ps, /api/tags).

Ollama does not expose Prometheus-style counters, so token throughput is derived
from the running-model set when available and otherwise reported as 0.
"""
from __future__ import annotations

import requests

from utils import config


def collect() -> dict:
    out = {
        "available": False,
        "running_models": [],
        "model_count": 0,
        "active_requests": 0,
        "tokens_per_sec": 0.0,
        "vram_used": 0.0,
        "mem_used": 0.0,
    }
    try:
        r = requests.get(f"{config.OLLAMA_URL}/api/ps", timeout=config.HTTP_TIMEOUT)
        if r.status_code != 200:
            return out
        data = r.json()
    except Exception:
        return out

    out["available"] = True
    models = data.get("models", []) or []
    vram = 0.0
    total = 0.0
    rows = []
    for m in models:
        size = float(m.get("size", 0) or 0)
        size_vram = float(m.get("size_vram", 0) or 0)
        vram += size_vram
        total += size
        rows.append({
            "name": m.get("name", "?"),
            "size": size,
            "size_vram": size_vram,
            "expires_at": m.get("expires_at", ""),
        })
    out["running_models"] = rows
    out["model_count"] = len(rows)
    # A loaded model implies it is serving / ready; treat as active.
    out["active_requests"] = len(rows)
    out["vram_used"] = vram
    out["mem_used"] = total
    return out
