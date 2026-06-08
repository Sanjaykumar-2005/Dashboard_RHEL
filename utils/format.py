"""Small human-readable formatting helpers."""
from __future__ import annotations


def bytes_h(n: float | int | None, unit_per_sec: bool = False) -> str:
    if n is None:
        return "N/A"
    n = float(n)
    suffix = "/s" if unit_per_sec else ""
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}{suffix}"
        n /= 1024.0
    return f"{n:.1f} EB{suffix}"


def num_h(n: float | int | None, decimals: int = 1) -> str:
    if n is None:
        return "N/A"
    n = float(n)
    for unit in ("", "K", "M", "B"):
        if abs(n) < 1000.0:
            return f"{n:.{decimals}f}{unit}"
        n /= 1000.0
    return f"{n:.{decimals}f}T"


def pct(n: float | None, decimals: int = 1) -> str:
    return "N/A" if n is None else f"{float(n):.{decimals}f}%"


def secs(n: float | None) -> str:
    if n is None:
        return "N/A"
    n = float(n)
    if n < 1.0:
        return f"{n * 1000:.0f} ms"
    return f"{n:.2f} s"
