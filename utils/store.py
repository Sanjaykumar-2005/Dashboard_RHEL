"""In-memory, thread-backed metric store — the heart of the dashboard.

A single background thread samples every collector once per second and appends a
full snapshot to a bounded ``deque``.  Nothing is written to disk or any
database; when a sample falls off the end of the deque it is gone forever.

All Streamlit pages share ONE store instance (created via ``@st.cache_resource``
in :func:`get_store`), so the rolling history is continuous regardless of which
page is being viewed, and the sampling cadence is independent of the UI refresh.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

from collectors import gpu, system, vllm, ollama, llm_perf, logs, journal
from utils import config


class MetricStore:
    def __init__(self, maxlen: int, interval: float):
        self.maxlen = maxlen
        self.interval = interval
        self._history: deque = deque(maxlen=maxlen)
        self._latest: dict = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.errors: dict[str, str] = {}
        # Collectors are independent and partly I/O-bound (nvidia-smi, HTTP to
        # vLLM/Ollama). Running them concurrently keeps each ~1s snapshot close
        # to the SLOWEST single source instead of their sum.
        self._pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="collector")

    # --- sampling ---------------------------------------------------------
    def _safe(self, name, fn, default):
        try:
            self.errors.pop(name, None)
            return fn()
        except Exception as exc:  # never let one collector kill the loop
            self.errors[name] = repr(exc)
            return default

    def _build_snapshot(self) -> dict:
        snap: dict = {"ts": time.time()}

        # Fan out the independent collectors.
        f_gpu = self._pool.submit(self._safe, "gpu", gpu.collect,
                                  {"available": False, "count": 0, "gpus": []})
        f_sys = self._pool.submit(self._safe, "system", system.collect, {})
        f_vllm = self._pool.submit(self._safe, "vllm", vllm.collect, {"available": False})
        f_oll = self._pool.submit(self._safe, "ollama", ollama.collect, {"available": False})
        f_log = self._pool.submit(self._safe, "logs", logs.collect,
                                  {"available": False, "rows": []})
        f_req = self._pool.submit(
            self._safe, "journal", journal.collect,
            {"vllm": {"available": False}, "ollama": {"available": False}})

        snap["gpu"] = f_gpu.result()
        sysm = f_sys.result()
        snap["cpu"] = sysm.get("cpu", {"available": False})
        snap["memory"] = sysm.get("memory", {"available": False})
        snap["disk"] = sysm.get("disk", {"available": False})
        snap["network"] = sysm.get("network", {"available": False})
        snap["vllm"] = f_vllm.result()
        snap["ollama"] = f_oll.result()
        snap["llm"] = llm_perf.collect(snap["vllm"], snap["ollama"])
        snap["logs"] = f_log.result()
        snap["requests"] = f_req.result()
        return snap

    def _run(self):
        while not self._stop.is_set():
            start = time.time()
            snap = self._build_snapshot()
            with self._lock:
                self._latest = snap
                self._history.append(snap)
            # Keep a steady ~interval cadence regardless of collection time.
            elapsed = time.time() - start
            self._stop.wait(max(0.0, self.interval - elapsed))

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="metric-sampler", daemon=True)
        self._thread.start()
        # Block briefly so the very first page render already has data.
        for _ in range(20):
            if self._latest:
                break
            time.sleep(0.05)

    def stop(self):
        self._stop.set()
        self._pool.shutdown(wait=False)

    # --- readers ----------------------------------------------------------
    def latest(self) -> dict:
        with self._lock:
            return dict(self._latest)

    def history(self) -> list[dict]:
        with self._lock:
            return list(self._history)

    def window(self, seconds: int) -> list[dict]:
        """Return snapshots from the last ``seconds`` seconds."""
        with self._lock:
            hist = list(self._history)
        if not hist:
            return []
        cutoff = hist[-1]["ts"] - seconds
        return [s for s in hist if s["ts"] >= cutoff]


# Streamlit wiring ---------------------------------------------------------
# get_store() must return the SAME instance for every page / session in the
# server process.  We import streamlit lazily so collectors stay testable
# without a Streamlit runtime.
def get_store() -> MetricStore:
    import streamlit as st

    @st.cache_resource(show_spinner=False)
    def _singleton() -> MetricStore:
        s = MetricStore(maxlen=config.HISTORY_LEN, interval=config.SAMPLE_INTERVAL)
        s.start()
        return s

    return _singleton()
