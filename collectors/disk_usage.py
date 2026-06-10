"""Find directories that occupy more than a size threshold (default 10 GB).

This is deliberately NOT part of the 1-second sampling loop: walking a large
filesystem (``du /``) can take tens of seconds, so the disk page calls
:func:`scan` behind ``st.cache_data`` with a long TTL + a manual "Rescan" button.

On Linux/RHEL we shell out to ``du`` (fast, C-implemented).  On a dev box without
``du`` (e.g. Windows) we fall back to a pure-Python ``os.scandir`` walk.
"""
from __future__ import annotations

import os
import shutil
import subprocess

from utils import config


def _du_scan(root: str, threshold: int, depth: int) -> list[dict]:
    """Use coreutils ``du`` — one line per dir up to ``depth``: ``SIZE\\tPATH``."""
    cmd = ["du", "-x", "--block-size=1", f"--max-depth={depth}", root]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    out: list[dict] = []
    root_norm = root.rstrip("/") or "/"
    for line in proc.stdout.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            parts = line.split(None, 1)
        if len(parts) != 2:
            continue
        try:
            size = int(parts[0])
        except ValueError:
            continue
        path = parts[1].strip()
        if path.rstrip("/") == root_norm:        # skip the root total itself
            continue
        if size >= threshold:
            out.append({"path": path, "bytes": size})
    out.sort(key=lambda d: d["bytes"], reverse=True)
    return out


def _walk_size(path: str) -> int:
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for f in filenames:
            try:
                total += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
    return total


def _py_scan(root: str, threshold: int, depth: int) -> list[dict]:
    """Cross-platform fallback when ``du`` is unavailable (slower)."""
    results: list[dict] = []

    def recurse(path: str, level: int) -> None:
        try:
            entries = list(os.scandir(path))
        except OSError:
            return
        for e in entries:
            try:
                is_dir = e.is_dir(follow_symlinks=False)
            except OSError:
                is_dir = False
            if not is_dir:
                continue
            size = _walk_size(e.path)
            if size >= threshold:
                results.append({"path": e.path, "bytes": size})
            if level < depth:
                recurse(e.path, level + 1)

    recurse(root, 1)
    results.sort(key=lambda d: d["bytes"], reverse=True)
    return results


def scan(root: str | None = None, threshold_bytes: int | None = None,
         depth: int | None = None) -> dict:
    """Return ``{"available", "root", "threshold", "dirs", "error"}``.

    ``dirs`` is a list of ``{"path", "bytes"}`` for directories at or above
    ``threshold_bytes``, largest first.
    """
    root = root or config.DISK_SCAN_ROOT
    threshold_bytes = threshold_bytes or config.DISK_SCAN_THRESHOLD_BYTES
    depth = depth or config.DISK_SCAN_DEPTH
    try:
        if shutil.which("du"):
            dirs = _du_scan(root, threshold_bytes, depth)
        else:
            dirs = _py_scan(root, threshold_bytes, depth)
        return {"available": True, "root": root, "threshold": threshold_bytes,
                "dirs": dirs, "error": None}
    except Exception as exc:  # timeout, permission, etc.
        return {"available": False, "root": root, "threshold": threshold_bytes,
                "dirs": [], "error": repr(exc)}
