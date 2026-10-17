#!/bin/bash
# Pre-ship checks on a pod after ship.sh (nothing else may hold the CPU): pyflakes (undefined names), cfgcheck.py (all 16
# yamls + base through the trainer's loader), REAL rl_royale --smoke with the ALL-ON yaml (fact16) and the base yaml, and
# the promotion eval's exact D3 command on 6 seeds with the factorial's full EXTRA (troops/eval_check.py, u250).
#   bash smoke.sh   -> /workspace/fact/smoke/{smoke.log, *.log, ev6/}, SMOKE_DONE
set -uo pipefail
CB=/workspace/cb_tt; PY=/workspace/venvf36/bin/python; O=/workspace/fact/smoke; FD=scratchpad/gauntlet/L74/factorial
mkdir -p $O; exec >> $O/smoke.log 2>&1
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=fork36-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
echo "$(date -u +%T) smoke start"
$PY -m pyflakes pipeline/{royale_runtime,royale_heroiw,royale_env,e1_eval,rl_royale,search_s0,reward_shaping}.py $FD/*.py \
  | grep -i "undefined\|syntax"; echo "pyflakes undefined-name / syntax lines above (none = clean)"
$PY $FD/cfgcheck.py
rm -rf scratchpad/gauntlet/L68/rl/smoke_fact16 scratchpad/gauntlet/L68/rl/smoke_fbase icebow/data/bench/rl_royale/smoke_fact16 \
  icebow/data/bench/rl_royale/smoke_fbase
$PY -m pipeline.rl_royale --config $FD/cfg/fact16.yaml --run smoke_fact16 --smoke > $O/smoke_fact16.log 2>&1 &
$PY -m pipeline.rl_royale --config scratchpad/gauntlet/L74/troops/gae_f36_u250.yaml --run smoke_fbase --smoke > $O/smoke_fbase.log 2>&1 &
rm -rf $O/ev6
$PY scratchpad/gauntlet/L74/troops/eval_check.py $O/ev6 6 --habit-log --live-levels --card-levels Rocket=16 Log=15 \
  --opp-tower-troops DaggerDuchess:0.028,Cannoneer:0.028,ChefTower:0.014 > $O/ev6.out 2>&1 &
wait
for s in smoke_fact16 smoke_fbase; do
  echo "$s: $(grep -c 'SMOKE PASS' $O/$s.log) SMOKE PASS; $(grep -o 'config sha [0-9a-f]*' $O/$s.log | head -1)"
done
echo "ev6: $(grep -c . $O/ev6/D3/matches.jsonl 2>/dev/null) rows, $(grep -c '"habits"' $O/ev6/D3/matches.jsonl 2>/dev/null) with habits, \
$(grep -c '"levels"' $O/ev6/D3/matches.jsonl 2>/dev/null) with levels"
echo "$(date -u +%T) smoke done"; touch $O/SMOKE_DONE
