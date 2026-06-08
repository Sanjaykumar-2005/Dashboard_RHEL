#!/usr/bin/env bash
# One-shot installer for RHEL 8 / 9.
# Creates a virtualenv and installs the dashboard dependencies.
set -euo pipefail

cd "$(dirname "$0")"

echo ">> Installing system packages (requires sudo)..."
# RHEL 8 ships Python 3.6; install 3.11 from AppStream. RHEL 9 has 3.9/3.11.
sudo dnf install -y python3.11 python3.11-pip pciutils || \
  sudo dnf install -y python3 python3-pip pciutils

PYBIN="$(command -v python3.11 || command -v python3)"
echo ">> Using interpreter: ${PYBIN}"

echo ">> Creating virtualenv..."
"${PYBIN}" -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate

echo ">> Upgrading pip and installing requirements..."
pip install --upgrade pip wheel
pip install -r requirements.txt

cat <<'EOF'

==========================================================
 Install complete.

 NOTE on NVIDIA NVML:
   - The `nvidia-ml-py` (pynvml) wheel needs the NVIDIA driver
     installed on the host. Verify with:  nvidia-smi
   - No extra CUDA toolkit is required for monitoring.

 Start the dashboard:
     ./run.sh
   or
     source venv/bin/activate
     streamlit run app.py --server.address=0.0.0.0 --server.port=8501

 Then open:  http://<server-ip>:8501
==========================================================
EOF
