# H200 Server Monitoring Dashboard

A lightweight, **real-time** monitoring dashboard for NVIDIA **H200** GPU servers
running **vLLM** / **Ollama** (Qwen 32B) on **RHEL 8/9**.

Built with **Streamlit + Plotly**. It reads live metrics directly from the system
and the LLM endpoints and refreshes **every 1 second**. **Nothing is persisted** —
no SQLite, PostgreSQL, MySQL, Prometheus, Grafana, or InfluxDB. All history is an
in-memory rolling buffer that disappears when the process stops.

---

## Pages

| # | Page | Source |
|---|------|--------|
| 0 | **Overview** (`app.py`) | everything, summarized |
| 1 | GPU Analytics | pynvml / nvidia-smi |
| 2 | CPU Analytics | psutil |
| 3 | Memory Analytics | psutil |
| 4 | Disk Analytics | psutil |
| 5 | Network Analytics | psutil |
| 6 | vLLM Analytics | vLLM `/metrics` (Prometheus text) |
| 7 | Ollama Analytics | Ollama `/api/ps` |
| 8 | LLM Performance | vLLM + Ollama (with P95/P99) |
| 9 | Request Analytics | tails an app request log (JSON lines) |
| 10 | Alerts | threshold engine over all sources |

## Architecture

```
app.py                       # Overview page + multipage entry point
pages/                       # one file per page (Streamlit auto-discovers)
collectors/                  # pure data readers -> plain dicts
  gpu.py        pynvml (NVML) with nvidia-smi fallback
  system.py     psutil cpu / memory / disk / network (+ rate deltas)
  vllm.py       scrapes & parses the vLLM Prometheus endpoint
  ollama.py     Ollama REST API
  llm_perf.py   aggregates vLLM + Ollama into serving KPIs
  logs.py       tails the request log (keeps a file offset)
utils/
  config.py     endpoints, thresholds, refresh rate (all env-overridable)
  store.py      MetricStore: ONE background thread samples every 1s into a
                bounded deque; shared across all pages via st.cache_resource
  charts.py     Plotly dark-theme chart helpers
  alerts.py     threshold evaluation
  format.py     human-readable bytes/numbers
  ui.py         page config, dark CSS, sidebar, 1s auto-refresh
.streamlit/config.toml       dark theme + server config
tools/simulate_requests.py   dev helper to generate a fake request log
```

**Why a background thread?** The UI refresh and the metric sampling are
decoupled. A single daemon thread (`utils/store.py`) samples every collector
once per second and appends a full snapshot to a `deque(maxlen=HISTORY_LEN)`.
Every page reads the same shared store, so the time-series stays continuous no
matter which page you're on, and rate metrics (disk/net/IOPS, token/s) are
computed from clean 1-second deltas.

---

## Install (RHEL 8 / 9)

```bash
# 1. Get the code onto the server, then:
cd /opt/h200-dashboard          # or wherever you cloned it
chmod +x install_rhel.sh run.sh
./install_rhel.sh               # creates venv/ and installs requirements
```

Manual equivalent:

```bash
sudo dnf install -y python3.11 python3.11-pip pciutils
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements.txt
```

> **GPU note:** `pynvml` (the `nvidia-ml-py` package) talks to the installed
> NVIDIA driver via NVML. Confirm the driver is present with `nvidia-smi`.
> No CUDA toolkit is needed just for monitoring.

---

## Run

```bash
./run.sh
# or explicitly:
source venv/bin/activate
streamlit run app.py --server.address=0.0.0.0 --server.port=8501 --server.headless=true
```

Open **http://<server-ip>:8501**.

Open the firewall if needed:

```bash
sudo firewall-cmd --add-port=8501/tcp --permanent
sudo firewall-cmd --reload
```

### Configuration (environment variables)

| Var | Default | Meaning |
|-----|---------|---------|
| `VLLM_METRICS_URL` | `http://localhost:8000/metrics` | vLLM Prometheus endpoint |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API base |
| `REQUEST_LOG_PATH` | `logs/requests.log` | JSON-lines request log to tail |
| `REFRESH_MS` | `1000` | UI auto-refresh interval |
| `SAMPLE_INTERVAL` | `1.0` | background sampling interval (s) |
| `HISTORY_LEN` | `900` | rolling samples kept in RAM (≈15 min) |
| `PORT` | `8501` | Streamlit port |

### Request log format

The Request Analytics page tails `REQUEST_LOG_PATH`, one JSON object per line:

```json
{"ts":"2026-06-08T10:00:00","user":"alice","model":"qwen2.5:32b","input_tokens":512,"output_tokens":128,"latency":0.84,"status":"ok"}
```

For a quick demo without a real workload:

```bash
source venv/bin/activate
python tools/simulate_requests.py     # writes synthetic records to logs/requests.log
```

---

## Run as a service (systemd)

```bash
sudo cp h200-dashboard.service /etc/systemd/system/
sudo mkdir -p /opt/h200-dashboard           # copy the project here
# Edit the User/Group/paths/Environment lines in the unit if needed.
sudo systemctl daemon-reload
sudo systemctl enable --now h200-dashboard
sudo systemctl status h200-dashboard
journalctl -u h200-dashboard -f             # live logs
```

---

## Alert rules

| Metric | Triggers when |
|--------|---------------|
| GPU Utilization | > 95 % |
| GPU Memory | > 90 % |
| GPU Temperature | > 85 °C |
| CPU Usage | > 95 % |
| Disk Usage | > 90 % |
| Queue Length | > 50 |
| TTFT | > 2 s |

Thresholds live in `utils/config.py` (`THRESHOLDS`).

---

## Notes / limitations

- The dashboard **degrades gracefully**: missing GPU, vLLM down, or no request
  log each show an informative message instead of crashing. You can develop it
  on a non-GPU laptop and CPU/RAM/disk/network panels still work.
- P95/P99 are approximated from the rolling history of vLLM's reported average
  latency (no per-request DB is kept, by design).
- Ollama exposes no token counters, so its tokens/sec is best-effort (0 unless a
  future API surfaces it); vLLM provides true token throughput.
