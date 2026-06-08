#!/usr/bin/env bash
# Start the H200 monitoring dashboard.
set -euo pipefail

cd "$(dirname "$0")"

# Activate venv if present.
if [[ -d "venv" ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

# Optional overrides (uncomment / edit as needed):
# export VLLM_METRICS_URL="http://localhost:8000/metrics"
# export OLLAMA_URL="http://localhost:11434"
# export REQUEST_LOG_PATH="/var/log/llm/requests.log"
# export REFRESH_MS=1000
# export HISTORY_LEN=900

exec streamlit run app.py \
  --server.address=0.0.0.0 \
  --server.port="${PORT:-8501}" \
  --server.headless=true
