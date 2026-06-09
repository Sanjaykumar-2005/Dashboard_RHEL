"""
Central configuration for the server monitoring dashboard.

Everything is overridable via environment variables so the same code runs on a
dev laptop and on the production RHEL box without edits.  No values are persisted
to disk — this module only describes *where* to read live metrics from.
"""
from __future__ import annotations

import json
import os


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


# --- Endpoints -------------------------------------------------------------
# vLLM exposes a Prometheus text endpoint (default :8009/metrics).
VLLM_METRICS_URL = _env("VLLM_METRICS_URL", "http://localhost:8009/metrics")
# LLM serving (Ollama) REST API base (default :8112).
OLLAMA_URL = _env("OLLAMA_URL", "http://localhost:8112")

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

# --- Journal-based request rates (systemd) ----------------------------------
# Request rates (req/sec, /min, /hour, /day) are derived by counting access-log
# lines in the systemd journal — no /metrics scrape required, so they work even
# when the Prometheus endpoint is down.  EVERYTHING here is env-overridable so no
# unit name or log pattern is hardcoded in the logic:
#   * units are comma-separated (a vLLM deployment may run several instances);
#   * the pattern is a journalctl --grep regex that matches exactly ONE line per
#     served request (the HTTP access-log line).
JOURNAL_ENABLED = _env("JOURNAL_ENABLED", "1").lower() not in ("0", "false", "no", "")
# How far back to seed the rolling counters on first sample (for the daily total).
JOURNAL_LOOKBACK = _env("JOURNAL_LOOKBACK", "24 hours ago")

# Which systemd units to count requests from lives in a separate, editable JSON
# file (journal_sources.json) so you can add/remove instances without touching
# code.  Precedence: env var (if set)  >  journal_sources.json  >  built-in default.
JOURNAL_SOURCES_FILE = _env("JOURNAL_SOURCES_FILE", "journal_sources.json")


def _load_journal_sources() -> dict:
    try:
        with open(JOURNAL_SOURCES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


_SOURCES = _load_journal_sources()


def _units(env_name: str, key: str, builtin: list[str]) -> list[str]:
    raw = os.environ.get(env_name)
    if raw and raw.strip():                       # env override wins
        return [u.strip() for u in raw.split(",") if u.strip()]
    units = _SOURCES.get(key, {}).get("units")    # then the JSON file
    if isinstance(units, list) and units:
        return [str(u).strip() for u in units if str(u).strip()]
    return builtin                                # finally the built-in default


def _pattern(env_name: str, key: str, builtin: str) -> str:
    raw = os.environ.get(env_name)
    if raw:
        return raw
    pat = _SOURCES.get(key, {}).get("request_pattern")
    return pat if isinstance(pat, str) and pat else builtin


VLLM_UNITS = _units("VLLM_UNITS", "vllm", ["chandra-api"])
VLLM_REQUEST_PATTERN = _pattern(
    "VLLM_REQUEST_PATTERN", "vllm", r"POST /v1/(chat/completions|completions|embeddings)")

OLLAMA_UNITS = _units("OLLAMA_UNITS", "ollama", ["ollama"])
OLLAMA_REQUEST_PATTERN = _pattern(
    "OLLAMA_REQUEST_PATTERN", "ollama", r"POST .*/api/(generate|chat|embeddings|embed)")

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

APP_TITLE = "Server Monitor"

# --- Sidebar navigation -----------------------------------------------------
# All pages grouped under a single "Analytics" dropdown in the sidebar
# (the native multipage list is disabled in .streamlit/config.toml).
# (label, script path relative to the app entry point).
PAGES = [
    ("Overview", "app.py"),
    ("GPU Analytics", "pages/1_GPU_Analytics.py"),
    ("CPU Analytics", "pages/2_CPU_Analytics.py"),
    ("Memory Analytics", "pages/3_Memory_Analytics.py"),
    ("Disk Analytics", "pages/4_Disk_Analytics.py"),
    ("Network Analytics", "pages/5_Network_Analytics.py"),
    ("vLLM Analytics", "pages/6_vLLM_Analytics.py"),
    ("Ollama Analytics", "pages/7_Ollama_Analytics.py"),
    ("LLM Performance", "pages/8_LLM_Performance.py"),
    ("Request Analytics", "pages/9_Request_Analytics.py"),
    ("Alerts", "pages/10_Alerts.py"),
]
