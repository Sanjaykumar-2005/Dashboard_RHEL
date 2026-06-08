"""Aggregated LLM serving performance, combining vLLM + Ollama signals.

Instantaneous values only.  Percentiles (P95/P99) are computed by the LLM
Performance page from the rolling in-memory history of these samples.
"""
from __future__ import annotations


def collect(vllm: dict, ollama: dict) -> dict:
    running = int(vllm.get("running", 0)) + int(ollama.get("active_requests", 0))
    queue = int(vllm.get("queue", 0))
    tokens = float(vllm.get("tokens_per_sec", 0.0)) + float(ollama.get("tokens_per_sec", 0.0))
    return {
        "available": bool(vllm.get("available") or ollama.get("available")),
        "requests_per_sec": float(vllm.get("success_per_sec", 0.0)),
        "concurrent_requests": running,
        "concurrent_users": running,          # 1 active request ~= 1 user, best-effort
        "queue": queue,
        "ttft": float(vllm.get("ttft", 0.0)),
        "avg_latency": float(vllm.get("e2e_latency", 0.0)),
        "tokens_per_sec": tokens,
        "active_models": int(ollama.get("model_count", 0)) + (1 if vllm.get("available") else 0),
    }
