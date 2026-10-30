#!/bin/bash
# repeat.sh CKPT -- PILOT-GATE determinism check (pod-side, 33903): the iu40 1-chunk block (12 games, seed 741200) again for the
# candidate (CPU 208) and for CLXIII (CPU 209), same env as dry_run.sh -> rows ev/rcand_iu40, ev/rbase_iu40.
CK=$1; P=/workspace/pgate
export GATE_CB=$P/cb GATE_PY=/workspace/venvf16/bin/python GATE_LIB=/workspace/crforge_main/5e8089a4/plain/lib \
  GATE_TABLES=/workspace/oplm/tables/16.635.3 GATE_FACADE=$P/facade GATE_EV=$P/ev CRFORGE_BARREL_DECOY_SIM=1 CRFORGE_XMX=1g \
  JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1" GATE_GAP=scratchpad/gauntlet/L74/plan1026/pilot/gate/gap_chunks.py
G=$P/cb/scratchpad/gauntlet/L74/plan1026/d2g/gate.sh
GAP_CHUNKS=1 GATE_CKPT=$CK bash $G crforge rcand_iu40 iu40 208 1 741200 > $P/rcand_iu40.out 2>&1 &
GAP_CHUNKS=1 bash $G crforge rbase_iu40 iu40 209 1 741200 > $P/rbase_iu40.out 2>&1 &
wait; echo "$(date -u +%FT%TZ) REPEAT DONE" > $P/REPEAT_DONE
