"""NVIDIA H200 GPU metrics via pynvml (NVML), with an nvidia-smi fallback."""
from __future__ import annotations

import shutil
import subprocess

try:
    import pynvml  # provided by the `nvidia-ml-py` package
    _HAVE_PYNVML = True
except Exception:  # pragma: no cover - import guard
    _HAVE_PYNVML = False

import psutil

_NVML_READY = False
_NVML_FAILED = False


def _ensure_nvml() -> bool:
    """Initialise NVML once.  Returns True if usable."""
    global _NVML_READY, _NVML_FAILED
    if _NVML_READY:
        return True
    if _NVML_FAILED or not _HAVE_PYNVML:
        return False
    try:
        pynvml.nvmlInit()
        _NVML_READY = True
        return True
    except Exception:
        _NVML_FAILED = True
        return False


def _decode(value) -> str:
    return value.decode() if isinstance(value, (bytes, bytearray)) else str(value)


def _proc_name(pid: int) -> str:
    try:
        return psutil.Process(pid).name()
    except Exception:
        return f"pid:{pid}"


def _collect_pynvml() -> dict:
    count = pynvml.nvmlDeviceGetCount()
    gpus = []
    for i in range(count):
        h = pynvml.nvmlDeviceGetHandleByIndex(i)
        g: dict = {"index": i}

        try:
            g["name"] = _decode(pynvml.nvmlDeviceGetName(h))
        except Exception:
            g["name"] = "NVIDIA GPU"

        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(h)
            g["util"] = float(util.gpu)
            g["mem_util_rate"] = float(util.memory)
        except Exception:
            g["util"] = 0.0
            g["mem_util_rate"] = 0.0

        try:
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            g["mem_total"] = float(mem.total)
            g["mem_used"] = float(mem.used)
            g["mem_free"] = float(mem.free)
            g["mem_util"] = (mem.used / mem.total * 100.0) if mem.total else 0.0
        except Exception:
            g["mem_total"] = g["mem_used"] = g["mem_free"] = g["mem_util"] = 0.0

        try:
            g["temp"] = float(pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU))
        except Exception:
            g["temp"] = 0.0

        try:
            g["power"] = pynvml.nvmlDeviceGetPowerUsage(h) / 1000.0  # mW -> W
        except Exception:
            g["power"] = 0.0
        try:
            g["power_limit"] = pynvml.nvmlDeviceGetEnforcedPowerLimit(h) / 1000.0
        except Exception:
            g["power_limit"] = 0.0

        try:
            g["clock_sm"] = float(pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_SM))
            g["clock_mem"] = float(pynvml.nvmlDeviceGetClockInfo(h, pynvml.NVML_CLOCK_MEM))
        except Exception:
            g["clock_sm"] = g["clock_mem"] = 0.0

        procs = []
        try:
            for p in pynvml.nvmlDeviceGetComputeRunningProcesses(h):
                procs.append({
                    "pid": p.pid,
                    "name": _proc_name(p.pid),
                    "mem": float(getattr(p, "usedGpuMemory", 0) or 0),
                })
        except Exception:
            pass
        g["processes"] = procs
        gpus.append(g)

    return _summarise(gpus)


def _collect_nvidia_smi() -> dict:
    """Fallback parser using the nvidia-smi CLI."""
    if shutil.which("nvidia-smi") is None:
        return {"available": False, "count": 0, "gpus": []}
    query = ("index,name,utilization.gpu,memory.used,memory.free,memory.total,"
             "temperature.gpu,power.draw,power.limit,clocks.sm,clocks.mem")
    try:
        out = subprocess.run(
            ["nvidia-smi", f"--query-gpu={query}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=2,
        )
        if out.returncode != 0:
            return {"available": False, "count": 0, "gpus": []}
    except Exception:
        return {"available": False, "count": 0, "gpus": []}

    gpus = []
    for line in out.stdout.strip().splitlines():
        f = [x.strip() for x in line.split(",")]
        if len(f) < 11:
            continue
        def num(x):
            try:
                return float(x)
            except Exception:
                return 0.0
        total, used = num(f[5]) * 1e6, num(f[3]) * 1e6  # MiB -> bytes approx
        gpus.append({
            "index": int(num(f[0])), "name": f[1],
            "util": num(f[2]),
            "mem_used": used, "mem_free": num(f[4]) * 1e6, "mem_total": total,
            "mem_util": (used / total * 100.0) if total else 0.0,
            "mem_util_rate": 0.0,
            "temp": num(f[6]), "power": num(f[7]), "power_limit": num(f[8]),
            "clock_sm": num(f[9]), "clock_mem": num(f[10]),
            "processes": [],
        })
    return _summarise(gpus)


def _summarise(gpus: list[dict]) -> dict:
    count = len(gpus)
    active = sum(1 for g in gpus if g.get("util", 0) > 0 or g.get("processes"))
    avg_util = (sum(g.get("util", 0) for g in gpus) / count) if count else 0.0
    avg_mem = (sum(g.get("mem_util", 0) for g in gpus) / count) if count else 0.0
    return {
        "available": count > 0,
        "count": count,
        "active": active,
        "avg_util": avg_util,
        "avg_mem_util": avg_mem,
        "gpus": gpus,
    }


def collect() -> dict:
    """Return a snapshot of all GPUs.  Prefers NVML, falls back to nvidia-smi."""
    if _ensure_nvml():
        try:
            return _collect_pynvml()
        except Exception:
            pass
    return _collect_nvidia_smi()
