#!/usr/bin/env bash
# faults.sh OUT [faults.py run args] -- D1-C HF fault count (pod 30408, /workspace/d1c). LIB = build_lib.sh output's lib/,
# FACADE = javac -d of this code copy's CfCore.java. Resumable per shard.
set -euo pipefail
OUT=$1; shift
CB=${D1C_CODE:-/workspace/d1c/cb}
export PYTHONPATH=$CB:/workspace/d1c/pylib:/workspace/cfspeed/pylib ROYALE_RUNTIME=fin16-linux ROYALE_ENGINE=crforge \
  CRFORGE_LIB=${CRFORGE_LIB:-/workspace/f635/rd_lib_bec5811a/lib} CRFORGE_FACADE_BUILD=${CRFORGE_FACADE_BUILD:-/workspace/d1c/build_new} \
  CRFORGE_TABLES=${CRFORGE_TABLES:-/workspace/f635/crforge_cache/tables/16.402.22} CRFORGE_XMX=${CRFORGE_XMX:-1g} \
  JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
exec /workspace/venvf16/bin/python -u "$CB/scratchpad/gauntlet/L74/plan1026/d1c/faults.py" run \
  --data "${D1C_DATA:-/workspace/d1c/hf/data}" --out "$OUT" "$@"
