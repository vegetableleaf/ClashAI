#!/bin/bash
# RT35 pod setup (2026-10-16, owner: "Let's do the re-baseline"): /workspace/venv35 = royalesim 0.1.35 + royalegym 0.1.23
# (0.1.35 requires no royalegym; gym 0.1.23 kept so the ENGINE is the one change) + venv33's extra deps at venv33's
# versions + venv33's torch. Run AFTER pod_setup_l74.sh + stage (venv33 with torch exists). Idempotent; venv33 untouched.
#   bash setup_rt35.sh [CB]     CB = a checkout holding rt35/build_manifest.json (default /workspace/clashbot)
#   -> /workspace/rt35_setup.log, /workspace/RT35_OK on success (activate() under ROYALE_RUNTIME=20261016-linux passed)
set -Eeuo pipefail
exec >> /workspace/rt35_setup.log 2>&1
trap 'echo "RT35 SETUP FAILED line $LINENO (exit $?)"; touch /workspace/RT35_FAILED' ERR
rm -f /workspace/RT35_FAILED /workspace/RT35_OK
CB=${1:-/workspace/clashbot}; V=/workspace/venv35; PY=$V/bin/python; P33=/workspace/venv33/bin/python
export UV_HTTP_TIMEOUT=600
echo "start $(date -u)"
[ -x $PY ] || uv venv -q --seed -p /usr/bin/python3 $V
uv pip freeze -p $P33 | grep -viE '^(royalesim|royalegym|torch|nvidia-|triton)' > /workspace/rt35_constraints.txt
uv pip install -q -p $PY -c /workspace/rt35_constraints.txt royalesim==0.1.35 royalegym==0.1.23 'maturin>=1.15,<2' \
    numpy msgspec pytest psutil orjson pyyaml jsonschema
TV=$($P33 -c "import torch; print(torch.__version__)")
$PY -c "import torch, sys; sys.exit(torch.__version__ != '$TV')" 2>/dev/null || \
  uv pip install -q -p $PY "torch==$TV" --index-url https://download.pytorch.org/whl/cu128
$PY -c "import importlib.metadata as m; print({k: m.version(k) for k in ('royalesim', 'royalegym', 'torch', 'numpy')})"
cd $CB
ROYALE_RUNTIME=20261016-linux PYTHONPATH=$CB PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  $PY -c "from pipeline.royale_runtime import activate; s = activate(); print(s['runtime_id'], s['pins'], s['card_table'])"
echo "done $(date -u)"
touch /workspace/RT35_OK
