#!/bin/bash
# closed_loop_probe.sh CKPT N OUT -- P4-10M: the D2-G crforge e4 gate worker (gap.py D3, all16, LIVE_OPTIONS decision stack,
# = d2g/devcost.sh's command) on the first N seeds of clxiii_cf_e4_741200's job 0 with CKPT as the learner (pod 33308).
# A compatibility / direction probe; the full check is d2g/gate.sh with GATE_CKPT + GATE_CB=/workspace/p4/cb_gate (480
# games per seed). cb_gate = /workspace/d2/cb (icebow/data symlinked) + memory/s1c/*.json + HEAD pipeline/model_gen.py
# (the d2 copy predates the P2-OPP1 options a step-trainer checkpoint carries).
CK=$1; N=$2; O=$3; CB=${PROBE_CB:-/workspace/p4/cb_gate}; PYX=/workspace/venvf16/bin/python
cd $CB || exit 1
unset ROYALE_HEROIW_PRESS
export HABITS_REC=1 PYTHONPATH=$CB:/workspace/d2/stage/pylib OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 ROYALE_HEROIW_FORM=hero O3_PLAYS=1 ROYALE_ENGINE=crforge ROYALE_RUNTIME=fin16-linux \
  CRFORGE_LIB=/workspace/d2/stage/lib CRFORGE_TABLES=/workspace/crforge_cache/tables/16.402.22 CRFORGE_FACADE_BUILD=/workspace/d2/build \
  CUDA_VISIBLE_DEVICES=
EX="--habit-log --live-levels --card-levels Rocket=16 Log=15 --ability-stats --ability-head-decode=sample --crown-log"
IN=/workspace/d2/ev/clxiii_cf_e4/clxiii_cf_e4_741200/inputs
ARGS=$("$PYX" scratchpad/gauntlet/L74/plan1026/d2g/prof_cmd.py "$IN" "$O" "$N" "$EX")
ARGS=${ARGS/icebow\/data\/models\/ICEBOW\/ICEBOW_Mark_CLXIII_NOLEAK.pt/$CK}
mkdir -p "$O"; echo "$ARGS" > "$O.cmd"
eval nice -n 10 "$PYX" "$ARGS" > "$O.log" 2>&1
echo "exit $? rows $(grep -c '"outcome"' "$O/matches.jsonl" 2>/dev/null)"
