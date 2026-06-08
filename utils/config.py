"""
Central configuration for the H200 monitoring dashboard.

Everything is overridable via environment variables so the same code runs on a
dev laptop and on the production RHEL box without edits.  No values are persisted
to disk — this module only describes *where* to read live metrics from.
"""
from __future__ import annotations

import os


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


# --- Endpoints -------------------------------------------------------------
# vLLM exposes a Prometheus text endpoint (default :8000/metrics).
VLLM_METRICS_URL = _env("VLLM_METRICS_URL", "http://localhost:8000/metrics")
# Ollama REST API base.
OLLAMA_URL = _env("OLLAMA_URL", "http://localhost:11434")

# HTTP timeout (seconds) for scraping the LLM endpoints.  Kept short so a dead
# endpoint never stalls the 1-second sampling loop.
HTTP_TIMEOUT = float(_env("HTTP_TIMEOUT", "0.8"))

# --- Request log ------------------------------------------------------------
# Path to the application request log that the Request Analytics page tails.
# Each line should be JSON, e.g.:
#   {"ts": "...", "user": "...", "model": "...", "input_tokens": 1,
#    "output_tokens": 1, "latency": 0.1, "status": "ok"}
# Plain text lines are still shown (raw) if they are not JSON.
REQUEST_LOG_PATH = _env("REQUEST_LOG_PATH", os.path.join("logs", "requests.log"))

# --- Sampling / history -----------------------------------------------------
# The background collector samples every SAMPLE_INTERVAL seconds; the UI also
# auto-refreshes at REFRESH_MS.  Both default to ~1 second per the spec.
SAMPLE_INTERVAL = float(_env("SAMPLE_INTERVAL", "1.0"))
REFRESH_MS = int(_env("REFRESH_MS", "1000"))

# Rolling, in-memory history length (number of 1-second samples kept).
# 900 samples == 15 minutes.  Nothing is written to any database.
HISTORY_LEN = int(_env("HISTORY_LEN", "900"))

# --- Alert thresholds (per spec) -------------------------------------------
THRESHOLDS = {
    "gpu_util": 95.0,      # GPU utilisation %
    "gpu_mem": 90.0,       # GPU memory %
    "gpu_temp": 85.0,      # GPU temperature °C
    "cpu": 95.0,           # CPU %
    "disk": 90.0,          # Disk usage %
    "queue": 50,           # LLM queue length
    "ttft": 2.0,           # Time-to-first-token (seconds)
}

# Selectable time ranges for the sidebar (label -> seconds of history shown).
TIME_RANGES = {
    "Last 30s": 30,
    "Last 1m": 60,
    "Last 5m": 300,
    "Last 15m": 900,
}

APP_TITLE = "H200 Server Monitor"
