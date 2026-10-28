#!/usr/bin/env bash
# run.sh LIBDIR OUT [redrive.py run args...] -- P2-RD1, the one command (pod 33308). LIBDIR = build_lib.sh's output
# (lib/ + BUILD.json); the facade (CfCore.java of this code copy) is compiled into LIBDIR/facade on first use.
# Re-run on a new crforge build: build_lib.sh FORK NEWREF NEWLIB (on the fork's pod), copy NEWLIB here, run.sh NEWLIB NEWOUT.
# Resumable: shards with OUT/shards/<sid>.json are skipped.
set -euo pipefail
LIB=$(readlink -f "$1"); OUT=$2; shift 2
CB=${RD_CODE:-/workspace/redrive/cb}
PY=${RD_PY:-/workspace/venvf16/bin/python}
if [ ! -f "$LIB/facade/CfCore.class" ]; then
  cp "$CB/scratchpad/gauntlet/L74/crforge/facade/CfCore.java" "$LIB/CfCore.java"
  mkdir -p "$LIB/facade" && javac -nowarn -cp "$LIB/lib/*" -d "$LIB/facade" "$LIB/CfCore.java"
fi
export PYTHONPATH=$CB:/workspace/redrive/pylib:/workspace/d2/stage/pylib ROYALE_RUNTIME=fin16-linux ROYALE_ENGINE=crforge \
  CRFORGE_LIB=$LIB/lib CRFORGE_FACADE_BUILD=$LIB/facade CRFORGE_TABLES=${CRFORGE_TABLES:-/workspace/crforge_cache/tables/16.402.22} \
  CRFORGE_XMX=${CRFORGE_XMX:-1g} JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  RD_CODE_HEAD=$(cat "$CB/CODE_HEAD" 2>/dev/null || echo unknown)
exec "$PY" -u "$CB/scratchpad/gauntlet/L74/plan1026/redrive/redrive.py" run --data "${RD_DATA:-/workspace/hf_il_replay/data}" --out "$OUT" "$@"
