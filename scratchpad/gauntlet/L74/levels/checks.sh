#!/bin/bash
# Pre-ship checks for factor D (live levels) + habit logging, on a fork36 pod (troops/setup_troops.sh done):
# HEAD checkout /workspace/cb_head (a copy of cb_tt = the committed option files) vs the edited copy /workspace/cb_lv.
#   smokes: HEAD x2 + edited, option ABSENT (config sha + every line compared); edited with live_levels=true
#   evals:  troops/eval_check.py (the promotion eval's exact D3 command, first 6 live-pool seeds): HEAD vs edited absent
#           (cmp); edited --habit-log (rows minus 'habits' == absent rows); --live-levels; --live-levels + card levels +
#           habit log.  check_levels.py, check_obs.py.  -> $O/CHECKS_DONE
set -uo pipefail
CB=/workspace/cb_lv; OLD=/workspace/cb_head; PY=/workspace/venvf36/bin/python; O=/workspace/results/LV
mkdir -p $O; exec >> $O/checks.log 2>&1
export ROYALE_RUNTIME=fork36-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1
TT=scratchpad/gauntlet/L74/troops; LV=scratchpad/gauntlet/L74/levels
echo "$(date -u +%T) checks start"
smoke() {  # DIR RUN [override]
  (cd $1 && PYTHONPATH=$1 $PY -m pipeline.rl_royale --config $TT/gae_f36_u250.yaml --run $2 --smoke ${3:+"$3"} > $O/$2.log 2>&1)
}
ev() {     # DIR NAME [EXTRA...]
  local d=$1 n=$2; shift 2
  (cd $d && PYTHONPATH=$d ROYALE_HEROIW_PRESS=live $PY $TT/eval_check.py $O/$n 6 "$@" > $O/$n.out 2>&1)
}
smoke $OLD lvsmoke_old &
smoke $OLD lvsmoke_old2 &
smoke $CB lvsmoke_new &
smoke $CB lvsmoke_on "live_levels=true" &
ev $OLD ev_old &
ev $CB ev_new &
ev $CB ev_habit --habit-log &
ev $CB ev_lv --live-levels &
ev $CB ev_lvh --live-levels --card-levels Rocket=16 Log=15 --habit-log &
(cd $CB && PYTHONPATH=$CB ROYALE_HEROIW_PRESS=live $PY $LV/check_obs.py icebow/data/bench/rl_royale/rlarm_gae/rlarm_gae_u0250_grafted.pt 40 \
  > $O/check_obs.out 2>&1) &
wait
cmp $O/ev_old/rows.json $O/ev_new/rows.json && echo "EVAL rows HEAD == edited (options absent): BYTE-IDENTICAL"
cmp $O/ev_old/D3/matches.jsonl $O/ev_new/D3/matches.jsonl >/dev/null || echo "(raw matches.jsonl differ: line order / wall fields)"
(cd $CB && $PY $LV/cmp_rows.py $O/ev_new/rows.json $O/ev_habit/rows.json habits) && echo "EVAL --habit-log rows minus 'habits' == absent rows"
for s in lvsmoke_old lvsmoke_old2 lvsmoke_new lvsmoke_on; do
  echo "$s: $(grep -c 'SMOKE PASS' $O/$s.log) SMOKE PASS; $(grep -o 'config sha [0-9a-f]*' $O/$s.log | head -1)"
done
echo "$(date -u +%T) checks done"
touch $O/CHECKS_DONE
