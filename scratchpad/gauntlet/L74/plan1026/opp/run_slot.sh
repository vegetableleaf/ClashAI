#!/usr/bin/env bash
# run_slot.sh LIBDIR OUT [redrive run args...] -- P2-OPP1 slot-row re-drive (pod 33308). Same env as redrive/run.sh;
# code copy OPP_CODE (default /workspace/opp/cb = a copy of the pass-1 /workspace/redrive/cb + this opp/ directory).
set -euo pipefail
LIB=$(readlink -f "$1"); OUT=$(readlink -f "$2"); shift 2
CB=${OPP_CODE:-/workspace/opp/cb}
PY=${RD_PY:-/workspace/venvf16/bin/python}
[ -f "$LIB/facade/CfCore.class" ] || { echo "facade not compiled in $LIB (run redrive/run.sh once)"; exit 2; }
export PYTHONPATH=$CB:/workspace/redrive/pylib:/workspace/d2/stage/pylib ROYALE_RUNTIME=fin16-linux ROYALE_ENGINE=crforge \
  CRFORGE_LIB=$LIB/lib CRFORGE_FACADE_BUILD=$LIB/facade CRFORGE_TABLES=${CRFORGE_TABLES:-/workspace/crforge_cache/tables/16.402.22} \
  CRFORGE_XMX=${CRFORGE_XMX:-1g} JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  RD_CODE_HEAD=$(cat "$CB/CODE_HEAD" 2>/dev/null || echo unknown) OPP_VOCAB=${OPP_VOCAB:-$CB/scratchpad/gauntlet/L74/plan1026/opp/vocab_hf.json}
cd "$OUT/.."
exec nice -n 10 "$PY" -u "$CB/scratchpad/gauntlet/L74/plan1026/opp/slot_redrive.py" run --data "${RD_DATA:-/workspace/hf_il_replay/data}" --out "$OUT" "$@"
