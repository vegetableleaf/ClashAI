#!/bin/bash
# pod_d3_loop.sh RUN SROOT EVCB CPUS WORKERS U0 [U1 ...] -- OPP-PUSH 10-31: arm_d3.sh's D3 block run ON the arm's own pod (no laptop:
# two laptop WMI loops died silently with empty logs). Same block: CLXIII live stack vs the arm, seed 741200, crforge 5e8089a4,
# tables 16.635.3, G2 on, opp T 1. SROOT = the arm's tree (its bench dir), EVCB = the eval code (33903 /workspace/opp/cb, booted
# pods /workspace/oplm/cbe). Appends "<time> RUN_uU [16.635.3] CLXIII W k / n" to /workspace/oplm/d3/RUN.d3.log.
# Start: setsid nohup bash pod_d3_loop.sh ... > /dev/null 2>&1 < /dev/null &   Stop: touch /workspace/oplm/d3/STOP_RUN (or kill PID).
RUN=$1; SROOT=$2; EVCB=$3; CPUS=$4; W=$5; shift 5
EV=/workspace/oplm/d3; SR=$SROOT/icebow/data/bench/rl_royale/$RUN; LOG=$EV/$RUN.d3.log; PY=/workspace/venvf16/bin/python
mkdir -p $EV/ck $EV/rows
for U in "$@"; do
  N=${RUN}_u$U
  until [ -f $SR/$N.pt ] || [ -f $EV/STOP_$RUN ]; do sleep 300; done
  [ -f $EV/STOP_$RUN ] && exit 0
  sleep 30; $PY /workspace/oplm/strip_ckpt.py $SR/$N.pt $EV/ck/$N.pt > /dev/null || { echo "$(date -u +%FT%TZ) $N strip failed" >> $LOG; continue; }
  (cd $EV && LIB=/workspace/crforge_main/5e8089a4/plain CB=$EVCB PY=$PY CRFORGE_TABLES=/workspace/oplm/tables/16.635.3 G2_ON=on \
    OPP_T=1.0 WORKERS=$W CPUS=$CPUS OPP_CKPT=$EV/ck/$N.pt bash $EVCB/scratchpad/gauntlet/L74/opp_model/humanlike/run_closed.sh $N $EV/rows/$N 741200 > $EV/$N.out 2>&1)
  F=$EV/rows/$N/${N}_741200/D3/matches.jsonl
  echo "$(date -u +%FT%TZ) $N [16.635.3] CLXIII W $(grep -c '"outcome": "win"' $F) / $(grep -c outcome $F)" >> $LOG
done
