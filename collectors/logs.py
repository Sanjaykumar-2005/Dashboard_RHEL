"""Tail the application request log in real time (no DB).

The reader keeps a file offset and only reads newly-appended lines on each call,
parsing JSON records into a normalised shape for the Request Analytics page.
Parsed rows are held in a bounded in-memory deque.
"""
from __future__ import annotations

import json
import os
import threading
from collections import deque

from utils import config

_MAXROWS = 500
_rows: deque = deque(maxlen=_MAXROWS)
_lock = threading.Lock()
_state = {"offset": 0, "inode": None}


def _normalise(obj: dict) -> dict:
    return {
        "timestamp": obj.get("ts") or obj.get("timestamp") or "",
        "user": obj.get("user", "-"),
        "model": obj.get("model", "-"),
        "input_tokens": obj.get("input_tokens", obj.get("prompt_tokens", 0)),
        "output_tokens": obj.get("output_tokens", obj.get("completion_tokens", 0)),
        "latency": obj.get("latency", obj.get("latency_s", 0.0)),
        "status": obj.get("status", "ok"),
    }


def collect() -> dict:
    path = config.REQUEST_LOG_PATH
    if not os.path.exists(path):
        with _lock:
            return {"available": False, "rows": list(_rows), "count": len(_rows)}

    try:
        st = os.stat(path)
        # Handle truncation / rotation: reset offset if the file shrank.
        if st.st_size < _state["offset"]:
            _state["offset"] = 0
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(_state["offset"])
            new_lines = f.readlines()
            _state["offset"] = f.tell()
    except Exception:
        with _lock:
            return {"available": False, "rows": list(_rows), "count": len(_rows)}

    with _lock:
        for line in new_lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                _rows.append(_normalise(obj))
            except Exception:
                # Keep non-JSON lines visible as raw entries.
                _rows.append({
                    "timestamp": "", "user": "-", "model": "-",
                    "input_tokens": 0, "output_tokens": 0,
                    "latency": 0.0, "status": "raw", "raw": line,
                })
        return {"available": True, "rows": list(_rows), "count": len(_rows)}
