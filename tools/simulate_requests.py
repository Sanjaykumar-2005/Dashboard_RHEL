"""Dev helper: append synthetic request records to the log so the Request
Analytics page has something to show without a live LLM workload.

Usage:  python tools/simulate_requests.py
This writes JSON-lines to logs/requests.log (or $REQUEST_LOG_PATH). It is NOT a
database — just an append-only application log, the same kind your real serving
app would produce.
"""
from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime

LOG = os.environ.get("REQUEST_LOG_PATH", os.path.join("logs", "requests.log"))
MODELS = ["qwen2.5:32b", "qwen2.5:32b-instruct", "llama3.1:70b"]
USERS = ["alice", "bob", "carol", "dave", "svc-batch"]

os.makedirs(os.path.dirname(LOG) or ".", exist_ok=True)
print(f"Writing synthetic requests to {LOG} (Ctrl-C to stop)...")

while True:
    rec = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "user": random.choice(USERS),
        "model": random.choice(MODELS),
        "input_tokens": random.randint(64, 2048),
        "output_tokens": random.randint(16, 1024),
        "latency": round(random.uniform(0.2, 3.5), 3),
        "status": random.choices(["ok", "error", "timeout"], weights=[92, 5, 3])[0],
    }
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    time.sleep(random.uniform(0.3, 1.5))
