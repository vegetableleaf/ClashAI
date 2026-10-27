#!/bin/bash
# S4 GPU bench bundle (plan1026 Pillar 4b): the 4090 grid on any CUDA GPU. Fresh RunPod PyTorch pod:
#   tar xzf gpu_bench.tgz -C /workspace && bash /workspace/gpu_bench/bench_gpu.sh
# Uses the image's torch if it imports with CUDA, else pip-installs torch (cu128). Writes /workspace/out/gpu_bench.json +
# /workspace/out/bench.log; the last line printed is DONE.
#   GRID=quick  -> 1.76M only (smoke)        default: 1.76M / 5M / 10M / 15M
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
O=${OUT:-/workspace/out}; mkdir -p "$O"
exec > >(tee "$O/bench.log") 2>&1
T0=$(date +%s)
echo "== env $(date -u)"; nvidia-smi --query-gpu=name,memory.total,driver_version,clocks.max.sm --format=csv || true
# A venv always (PEP 668 images refuse pip); it sees the image's torch unless FRESH=1 (then torch cu128 is installed).
BASE=${PYBIN:-python3}
if [ "${FRESH:-0}" = 1 ]; then "$BASE" -m venv /workspace/gbvenv; else "$BASE" -m venv --system-site-packages /workspace/gbvenv; fi
PY=/workspace/gbvenv/bin/python
if ! "$PY" -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)" 2>/dev/null; then
  echo "== no CUDA torch visible: installing torch (cu128) into the venv"
  "$PY" -m pip install -q --upgrade pip && "$PY" -m pip install -q torch --index-url https://download.pytorch.org/whl/cu128
fi
"$PY" -c "import numpy, pytest, yaml, orjson" 2>/dev/null || "$PY" -m pip install -q numpy pytest pyyaml orjson
"$PY" -c "import torch; print('== torch', torch.__version__, 'cuda', torch.version.cuda, 'cudnn', torch.backends.cudnn.version(), torch.cuda.get_device_name(0))"
echo "== setup $(( $(date +%s) - T0 )) s"
cd "$HERE"; export PYTHONPATH="$HERE" PYTHONDONTWRITEBYTECODE=1
S=scratchpad/gauntlet/L74/speed
SIZES=1.76M,5M,10M,15M; [ "${GRID:-full}" = quick ] && SIZES=1.76M
"$PY" $S/s4_bench.py --part precision --sizes $SIZES --out "$O/precision.json" || echo "precision FAILED"
echo "== precision done $(( $(date +%s) - T0 )) s"
"$PY" $S/s4_bench.py --part forward --modes eager,graphs --sizes $SIZES --out "$O/forward.json" || echo "forward FAILED"
echo "== forward done $(( $(date +%s) - T0 )) s"
"$PY" - "$O" "$(( $(date +%s) - T0 ))" <<'EOF'
import json, sys, torch
from pathlib import Path
o = Path(sys.argv[1])
res = {"gpu": torch.cuda.get_device_name(0), "torch": torch.__version__, "cuda": torch.version.cuda,
       "cudnn": torch.backends.cudnn.version(), "wall_s": int(sys.argv[2])}
for k in ("precision", "forward"):
    p = o / f"{k}.json"
    res[k] = json.loads(p.read_text())["rows"] if p.exists() else None
(o / "gpu_bench.json").write_text(json.dumps(res, indent=1))
print("wrote", o / "gpu_bench.json")
EOF
echo DONE
