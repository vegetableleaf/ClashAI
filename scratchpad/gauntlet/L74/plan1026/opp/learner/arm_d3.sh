#!/bin/bash
# arm_d3.sh RUN SRCPORT EVALPORT CPUS WORKERS U0 [U1 ...] -- lead 10-29, one loop per opponent-calibration arm.
# For each update U: wait for SRC:<bench>/RUN/RUN_uU.pt, strip it (strip_ckpt.py), move it to the eval pod, run one 480-game
# D3 block (CLXIII live stack vs the arm, seed 741200, crforge fe364ceb, G2 on, opp T 1) on the LIVE tables 16.635.3
# (earlier blocks used 16.402.22 = an old client; live runs 16.635.3 per CRFORGE_S0.md), print the CLXIII win count.
# Pod layout: 33308 arms in /workspace/oplc (bench via cb2 -> /workspace/d2/cb), others in /workspace/oplm/cb2.
# Stop: touch STOP_ARM_D3 next to this script. Never edit this file while a loop runs (run a copy).
RUN=$1; SP=$2; EP=$3; CPUS=$4; W=$5; shift 5
S="ssh -o BatchMode=yes -o ConnectTimeout=30 -i $HOME/.ssh/runpod_clashbot root@157.157.221.29 -p"
STOP=$(dirname "$0")/STOP_ARM_D3
root() { [ "$1" = 33308 ] && echo /workspace/oplc/cb2 || echo /workspace/oplm/cb2; }
py() { case $1 in 33553) echo /workspace/venv/bin/python;; 30408) echo /workspace/siege/venv/bin/python;; *) echo /workspace/venvf16/bin/python;; esac; }
tab() { [ "$1" = 33308 ] && echo /workspace/crforge_cache/tables/16.635.3 || echo /workspace/oplm/tables/16.635.3; }
evcb() { [ "$1" = 33903 ] && echo /workspace/opp/cb || echo /workspace/oplm/cbe; }   # level-B eval code (cb2 lacks opp_model/)
SR=$(root $SP)/icebow/data/bench/rl_royale/$RUN; ER=$(evcb $EP); EV=/workspace/oplm/d3
H=$ER/scratchpad/gauntlet/L74/opp_model/humanlike
for U in "$@"; do
  N=${RUN}_u$U
  until $S $SP "test -f $SR/$N.pt" || [ -f "$STOP" ]; do sleep 300; done
  [ -f "$STOP" ] && exit 0
  $S $SP "$(py $SP) /workspace/oplm/strip_ckpt.py $SR/$N.pt /workspace/oplm/strip_$N.pt >/dev/null" || { echo "$N strip failed"; continue; }
  $S $EP "mkdir -p $EV/ck"
  if [ "$SP" = "$EP" ]; then $S $SP "mv /workspace/oplm/strip_$N.pt $EV/ck/$N.pt"
  else $S $SP "cat /workspace/oplm/strip_$N.pt && rm -f /workspace/oplm/strip_$N.pt" | $S $EP "cat > $EV/ck/$N.pt"; fi
  $S $EP "cd $EV && CB=$ER PY=$(py $EP) CRFORGE_TABLES=$(tab $EP) G2_ON=on OPP_T=1.0 WORKERS=$W CPUS=$CPUS OPP_CKPT=$EV/ck/$N.pt bash $H/run_closed.sh $N $EV/rows/$N 741200 > $EV/$N.out 2>&1"
  F=$EV/rows/$N/${N}_741200/D3/matches.jsonl
  echo "$(date -u +%FT%TZ) $N [16.635.3] CLXIII W $($S $EP "grep -c '\"outcome\": \"win\"' $F") / $($S $EP "grep -c outcome $F")"
done
