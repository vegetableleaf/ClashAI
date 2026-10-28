#!/usr/bin/env bash
# hf_run.sh OUT.npz [hf_traces.py args] -- on pod 33308, the re-drive's engine env (redrive/run.sh) around hf_traces.py.
# CB = a code copy with this rx/ overlaid (default /workspace/rx_hf/cb); LIB = the re-drive's crforge build.
set -euo pipefail
CB=${RX_CB:-/workspace/rx_hf/cb}
LIB=${RX_LIB:-/workspace/redrive/rd_lib_bec5811a}
export PYTHONPATH=$CB:/workspace/redrive/pylib:/workspace/d2/stage/pylib ROYALE_RUNTIME=fin16-linux ROYALE_ENGINE=crforge \
  CRFORGE_LIB=$LIB/lib CRFORGE_FACADE_BUILD=$LIB/facade CRFORGE_TABLES=${CRFORGE_TABLES:-/workspace/crforge_cache/tables/16.402.22} \
  CRFORGE_XMX=${CRFORGE_XMX:-1g} JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1" OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  RX_CATALOG=${RX_CATALOG:-$CB/research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json} \
  RX_STATS=${RX_STATS:-$CB/icebow/config/cards_stats.json} RX_SIMCARDS=${RX_SIMCARDS:-/workspace/rx_hf/simcards.json}
exec /workspace/venvf16/bin/python -u "$CB/scratchpad/gauntlet/L74/plan1026/rx/hf_traces.py" /workspace/hf_il_replay/data "$@"
