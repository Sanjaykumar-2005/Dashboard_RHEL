"""Request-rate counters derived from the systemd journal — no /metrics needed.

Every served request leaves exactly one HTTP access-log line in the journal
(uvicorn for vLLM, Gin for Ollama).  We count those lines per unit-group and
turn them into req/sec, req/min, req/hour and req/day.  This keeps working even
when the Prometheus ``/metrics`` endpoint is down, which is the whole point.

How it stays cheap and dynamic:
  * ``journalctl --grep=<pattern>`` filters server-side, so only request lines
    come back — the pattern, the unit names and the lookback are all config /
    env driven (see utils/config.py); nothing here is hardcoded.
  * First sample seeds the last ``JOURNAL_LOOKBACK`` (for the daily total) and
    records the journal cursor; every later sample reads only entries
    ``--after-cursor`` the last one, so per-tick work is tiny.
  * Event timestamps are kept in a sorted list pruned to 24h; window counts use
    bisect (O(log n)).
"""
from __future__ import annotations

import bisect
import json
import shutil
import subprocess
import threading
import time

from utils import config

_DAY = 86400


class _Source:
    """Rolling request-event counter for one group of systemd units."""

    def __init__(self, units: list[str], pattern: str):
        self.units = units
        self.pattern = pattern
        self._events: list[float] = []     # epoch seconds, ascending
        self._cursor: str | None = None
        self._seeded = False
        self._total = 0                    # cumulative since process start
        self._lock = threading.Lock()
        self._error: str | None = None

    # -- journalctl plumbing ------------------------------------------------
    def _base_cmd(self) -> list[str]:
        cmd = ["journalctl", "-o", "json", "--no-pager", "-q"]
        for u in self.units:
            cmd += ["-u", u]
        if self.pattern:
            cmd += ["--grep", self.pattern]
        return cmd

    def _run(self, extra: list[str]) -> list[dict] | None:
        try:
            proc = subprocess.run(
                self._base_cmd() + extra,
                capture_output=True, text=True, timeout=8,
            )
        except FileNotFoundError:
            self._error = "journalctl not found (not a systemd host)"
            return None
        except Exception as exc:  # timeout etc.
            self._error = repr(exc)
            return None

        err = (proc.stderr or "").strip()
        if err and ("permission" in err.lower() or "failed" in err.lower()):
            # e.g. dashboard user not in systemd-journal group.
            self._error = err.splitlines()[0]
            return None

        self._error = None
        entries = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except ValueError:
                continue
        return entries

    @staticmethod
    def _ts(entry: dict) -> float | None:
        raw = entry.get("__REALTIME_TIMESTAMP")
        if raw is None:
            return None
        try:
            return int(raw) / 1_000_000.0
        except (TypeError, ValueError):
            return None

    def _ingest(self, entries: list[dict]) -> None:
        for e in entries:
            ts = self._ts(e)
            if ts is not None:
                self._events.append(ts)
                self._total += 1
            cur = e.get("__CURSOR")
            if cur:
                self._cursor = cur

    # -- public sample ------------------------------------------------------
    def sample(self) -> dict:
        with self._lock:
            if not self._seeded:
                entries = self._run(["--since", config.JOURNAL_LOOKBACK])
                if entries is None:
                    return self._result(available=False)
                self._ingest(entries)
                self._seeded = True
            else:
                after = ["--after-cursor", self._cursor] if self._cursor else \
                    ["--since", config.JOURNAL_LOOKBACK]
                entries = self._run(after)
                if entries is None:
                    return self._result(available=False)
                self._ingest(entries)

            return self._result(available=True)

    def _result(self, available: bool) -> dict:
        now = time.time()
        # Drop events older than a day (keeps memory bounded; list stays sorted).
        cut = bisect.bisect_left(self._events, now - _DAY)
        if cut:
            del self._events[:cut]

        def since(window: int) -> int:
            return len(self._events) - bisect.bisect_left(self._events, now - window)

        # Calendar-day total: count from local midnight (12 AM) so the number
        # only climbs through the day and resets to 0 at the next midnight,
        # instead of a rolling 24h window that "reduces" during quiet stretches.
        lt = time.localtime(now)
        midnight = now - (lt.tm_hour * 3600 + lt.tm_min * 60 + lt.tm_sec)
        req_today = len(self._events) - bisect.bisect_left(self._events, midnight)

        per_min = since(60)
        return {
            "available": available,
            "units": self.units,
            "error": self._error,
            # req/sec smoothed over the last minute to avoid 0/1 jitter.
            "req_per_sec": round(per_min / 60.0, 2),
            "req_per_min": per_min,
            "req_per_hour": since(3600),
            "req_per_day": req_today,   # since local midnight (resets at 12 AM)
            "total_seen": self._total,
        }


_HAVE_JOURNALCTL = shutil.which("journalctl") is not None
_vllm = _Source(config.VLLM_UNITS, config.VLLM_REQUEST_PATTERN)
_ollama = _Source(config.OLLAMA_UNITS, config.OLLAMA_REQUEST_PATTERN)


def tail(units: list[str], lines: int = 60) -> dict:
    """Return the last ``lines`` raw journal lines for the given units.

    Used to render live service logs under each page's charts.  Unlike
    :meth:`_Source.sample`, this is unfiltered (no ``--grep``) so it shows the
    full service output, not just request lines.
    """
    if not config.JOURNAL_ENABLED or not _HAVE_JOURNALCTL:
        return {"available": False, "lines": [],
                "error": "journalctl unavailable on this host"}
    cmd = ["journalctl", "--no-pager", "-q", "-n", str(lines)]
    for u in units:
        cmd += ["-u", u]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
    except FileNotFoundError:
        return {"available": False, "lines": [],
                "error": "journalctl not found (not a systemd host)"}
    except Exception as exc:  # timeout etc.
        return {"available": False, "lines": [], "error": repr(exc)}

    err = (proc.stderr or "").strip()
    if err and ("permission" in err.lower() or "failed" in err.lower()):
        return {"available": False, "lines": [], "error": err.splitlines()[0]}

    out = [ln for ln in proc.stdout.splitlines() if ln.strip()]
    return {"available": True, "lines": out, "error": None}


def _empty(units: list[str]) -> dict:
    return {
        "available": False, "units": units, "error": None,
        "req_per_sec": 0.0, "req_per_min": 0, "req_per_hour": 0,
        "req_per_day": 0, "total_seen": 0,
    }


def collect() -> dict:
    """Return request-rate counters for the vLLM and Ollama unit groups."""
    if not config.JOURNAL_ENABLED or not _HAVE_JOURNALCTL:
        return {"vllm": _empty(config.VLLM_UNITS),
                "ollama": _empty(config.OLLAMA_UNITS)}
    return {"vllm": _vllm.sample(), "ollama": _ollama.sample()}
