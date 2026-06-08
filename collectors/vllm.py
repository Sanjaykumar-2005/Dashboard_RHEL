"""vLLM metrics — scraped from its Prometheus text endpoint (/metrics).

We parse the exposition format by hand (no prometheus_client dependency) and
turn monotonic counters into per-second rates using the delta between scrapes.
"""
from __future__ import annotations

import time

import requests

from utils import config

# Counter state for rate computation: name -> (value, timestamp).
_prev_counters: dict[str, tuple[float, float]] = {}


def _parse_prometheus(text: str) -> dict[str, float]:
    """Very small Prometheus text parser.

    Returns a map of "metric{labels}" -> value plus convenient aggregates where
    the same metric appears across label sets (summed) for *_total counters and
    summed gauges for the request-state metrics.
    """
    samples: dict[str, float] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # split "metric{labels} value [timestamp]"
        try:
            if "{" in line:
                name = line[: line.index("{")]
                rest = line[line.rindex("}") + 1:].strip()
            else:
                name, rest = line.split(None, 1)
            value = float(rest.split()[0])
        except (ValueError, IndexError):
            continue
        samples[name] = samples.get(name, 0.0) + value
    return samples


def _rate(name: str, value: float, now: float) -> float:
    prev = _prev_counters.get(name)
    _prev_counters[name] = (value, now)
    if prev is None:
        return 0.0
    pv, pt = prev
    dt = now - pt
    if dt <= 0 or value < pv:  # reset / no time elapsed
        return 0.0
    return (value - pv) / dt


def _hist_avg(samples: dict[str, float], base: str) -> float:
    """Average of a Prometheus histogram/summary: _sum / _count (cumulative)."""
    s = samples.get(base + "_sum")
    c = samples.get(base + "_count")
    if s is None or not c:
        return 0.0
    return s / c


def collect() -> dict:
    out = {
        "available": False,
        "running": 0,
        "pending": 0,
        "queue": 0,
        "batch_size": 0,
        "tokens_per_sec": 0.0,
        "prompt_tokens_per_sec": 0.0,
        "gpu_cache_usage": 0.0,
        "ttft": 0.0,
        "e2e_latency": 0.0,
        "success_per_sec": 0.0,
    }
    try:
        r = requests.get(config.VLLM_METRICS_URL, timeout=config.HTTP_TIMEOUT)
        if r.status_code != 200:
            return out
        s = _parse_prometheus(r.text)
    except Exception:
        return out

    now = time.time()
    out["available"] = True
    out["running"] = int(s.get("vllm:num_requests_running", 0))
    out["pending"] = int(s.get("vllm:num_requests_waiting", 0))
    out["queue"] = out["pending"]
    # Running batch == requests currently being decoded.
    out["batch_size"] = out["running"]
    out["gpu_cache_usage"] = s.get("vllm:gpu_cache_usage_perc", 0.0) * 100.0

    out["tokens_per_sec"] = _rate(
        "gen_tok", s.get("vllm:generation_tokens_total", 0.0), now)
    out["prompt_tokens_per_sec"] = _rate(
        "prompt_tok", s.get("vllm:prompt_tokens_total", 0.0), now)
    out["success_per_sec"] = _rate(
        "success", s.get("vllm:request_success_total", 0.0), now)

    out["ttft"] = _hist_avg(s, "vllm:time_to_first_token_seconds")
    out["e2e_latency"] = _hist_avg(s, "vllm:e2e_request_latency_seconds")
    return out
