#!/bin/bash
# dry_run.sh CKPT -- PILOT-GATE 10-30 dry run on 33903 (pod-side): gate.sh on crforge 5e8089a4 + tables 16.635.3, candidate CKPT and
# base CLXIII NOLEAK, e4 3 chunks (36 games) on 3 CPUs each + iu40 1 chunk (12 games) on 1 CPU each = CPUs 202-209.
# Rows: /workspace/pgate/ev/<tag>/...; logs /workspace/pgate/<tag>.out. Same env as the full gate (GATE_AND_LIVE.md step 1).
CK=$1; P=/workspace/pgate
export GATE_CB=$P/cb GATE_PY=/workspace/venvf16/bin/python GATE_LIB=/workspace/crforge_main/5e8089a4/plain/lib \
  GATE_TABLES=/workspace/oplm/tables/16.635.3 GATE_FACADE=$P/facade GATE_EV=$P/ev CRFORGE_BARREL_DECOY_SIM=1 CRFORGE_XMX=1g \
  JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1" GATE_GAP=scratchpad/gauntlet/L74/plan1026/pilot/gate/gap_chunks.py
G=$P/cb/scratchpad/gauntlet/L74/plan1026/d2g/gate.sh
GAP_CHUNKS=3 GATE_CKPT=$CK bash $G crforge dcand_e4 e4 202-204 3 741200 > $P/dcand_e4.out 2>&1 &
GAP_CHUNKS=3 bash $G crforge dbase_e4 e4 205-207 3 741200 > $P/dbase_e4.out 2>&1 &
GAP_CHUNKS=1 GATE_CKPT=$CK bash $G crforge dcand_iu40 iu40 208 1 741200 > $P/dcand_iu40.out 2>&1 &
GAP_CHUNKS=1 bash $G crforge dbase_iu40 iu40 209 1 741200 > $P/dbase_iu40.out 2>&1 &
wait; echo "$(date -u +%FT%TZ) DRY DONE" > $P/DRY_DONE
