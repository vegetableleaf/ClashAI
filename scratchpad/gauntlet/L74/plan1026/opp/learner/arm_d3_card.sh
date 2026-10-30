#!/bin/bash
# arm_d3_card.sh RUN SRCPORT EVALPORT CPUS WORKERS U0 [U1 ...] -- OPP-PUSH 10-30: arm_d3.sh (sha 519be4b0, unchanged D3 block:
# CLXIII live stack vs the arm, seed 741200, crforge 5e8089a4, tables 16.635.3, G2 on, opp T 1) + the v6 QUICK CARD after each
# block (rows fetched to the laptop, card.py score --no-c --no-d: B-live RMS + siege facts; sealed block never opened).
# Prints two lines per update: arm_d3.sh's "CLXIII W k / n" line, then "CARD <name> RMS .. z-fails .. lock .. zero .. plf ..".
# Local rows / reports (bulk, not committed): .foreman/scratch/opp_push/{rows,card}/NAME.
# Stop: touch STOP_ARM_D3 next to the running copy. Never edit a running copy (run a copy with a new name per loop).
RUN=$1; SP=$2; EP=$3; CPUS=$4; W=$5; shift 5
S="ssh -o BatchMode=yes -o ConnectTimeout=30 -i $HOME/.ssh/runpod_clashbot root@157.157.221.29 -p"
STOP=$(dirname "$0")/STOP_ARM_D3
REPO=/c/Users/benpe/ClashBot; LR=$REPO/.foreman/scratch/opp_push
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
  $S $EP "cd $EV && LIB=/workspace/crforge_main/5e8089a4/plain CB=$ER PY=$(py $EP) CRFORGE_TABLES=$(tab $EP) G2_ON=on OPP_T=1.0 WORKERS=$W CPUS=$CPUS OPP_CKPT=$EV/ck/$N.pt bash $H/run_closed.sh $N $EV/rows/$N 741200 > $EV/$N.out 2>&1"
  F=$EV/rows/$N/${N}_741200/D3/matches.jsonl
  echo "$(date -u +%FT%TZ) $N [16.635.3] CLXIII W $($S $EP "grep -c '\"outcome\": \"win\"' $F") / $($S $EP "grep -c outcome $F")"
  # quick card (laptop, ~30 s): rows -> card.py score --no-c --no-d
  mkdir -p $LR/rows/$N $LR/card
  $S $EP "cd $EV/rows/$N && tar czf - ENGINE.json */D3/matches.jsonl" | tar xzf - -C $LR/rows/$N \
    && (cd $REPO && icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/opp_model/humanlike/card.py score --name $N \
        --sim $LR/rows/$N --no-c --no-d --out $LR/card/$N > $LR/card/$N.log 2>&1) \
    && echo "$(date -u +%FT%TZ) CARD $N $(grep -h 'B-live pooled' $LR/card/$N/report.txt | grep -o 'RMS d over [0-9]* stats [0-9.]*\|TOST all [A-Za-z]* ([0-9]* fail)' | tr '\n' ' ')$(grep -h -E '^  (lock_rate|zero_lock|p_lock_after_fail):' $LR/card/$N/report.txt | awk '{printf "%s %s ", $1, $5}')" \
    || echo "$(date -u +%FT%TZ) CARD $N FAILED (see $LR/card/$N.log)"
done
