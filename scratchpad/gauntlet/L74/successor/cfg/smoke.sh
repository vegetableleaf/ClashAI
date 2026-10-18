#!/bin/bash
# Pod pre-flight after ship.sh, ONLY on an idle pod (refuses while any factorial / RL / eval python runs): cfgcheck.py (every
# successor yaml through the trainer's loader + the one-change diff vs succ_ctl) and a REAL rl_royale --smoke of every
# succ_* job in this pod's queue (fork36-linux, Hero IW). The code is the factorial's checkout (pyflakes passed there).
#   bash /workspace/succ/smoke.sh   -> /workspace/succ/smoke/{smoke.log, <run>.log}, SMOKE_OK only when everything passed
set -uo pipefail
CB=/workspace/cb_tt; PY=/workspace/venvf36/bin/python; F=/workspace/succ; O=$F/smoke; FD=scratchpad/gauntlet/L74/successor/cfg
mkdir -p $O; exec >> $O/smoke.log 2>&1; rm -f $O/SMOKE_OK
busy=$(ps -eo args | grep -v grep | grep -cE "python.*(rl_royale|gap\.py|search_s0|livecal|e1_eval)")
[ "$busy" = 0 ] || { echo "$(date -u +%T) pod busy ($busy python jobs): no smoke"; exit 2; }
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=fork36-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
echo "$(date -u +%T) smoke start"
$PY $FD/cfgcheck.py; ok=$?
runs=$(grep -oE "^succ_[a-z0-9_]+" $F/queue.txt | sort -u)
for r in $runs; do
  rm -rf scratchpad/gauntlet/L68/rl/smoke_$r icebow/data/bench/rl_royale/smoke_$r
  $PY -m pipeline.rl_royale --config $FD/$r.yaml --run smoke_$r --smoke > $O/$r.log 2>&1 &
done
wait
for r in $runs; do
  n=$(grep -c 'SMOKE PASS' $O/$r.log); echo "$r: $n SMOKE PASS; $(grep -o 'config sha [0-9a-f]*' $O/$r.log | head -1)"
  [ "$n" -ge 1 ] || ok=1
done
[ $ok = 0 ] && touch $O/SMOKE_OK; echo "$(date -u +%T) smoke done (ok=$ok)"
