#!/usr/bin/env bash
# One-shot environment setup for the GPU workstation (tested target: RTX 5080, Blackwell → CUDA 12.8 wheels).
# Usage:  bash scripts/setup_gpu.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3}
$PY -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip wheel

# RTX 50-series needs a CUDA 12.8+ build of PyTorch; older wheels fail with "no kernel image".
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
pip install -e .

python - <<'EOF'
import torch
print("torch", torch.__version__, "cuda", torch.cuda.is_available(),
      torch.cuda.get_device_name(0) if torch.cuda.is_available() else "")
EOF
OMP_NUM_THREADS=1 python -m pytest -q
echo "setup OK — now run:  bash scripts/run_all.sh"
