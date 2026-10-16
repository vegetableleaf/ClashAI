#!/bin/bash
# S2 fight-level parity scoreboard (fights.py) on royalesim 0.1.35 (ROYALE_RUNTIME=20261016-linux, /workspace/venv35)
# over every frame-logged live match. Needs the live logs on the pod under $LIVE (copy from the laptop first, see
# PARITY_SCOREBOARD.md). Serialised on /workspace/cpu.lock; results $O/{matches/,SCOREBOARD_{strict,core,all}.txt,
# scoreboard_*.json,run.log,DONE}. Rerunning skips matches already in $O/matches.
#   nohup bash scratchpad/gauntlet/L74/parity/run_fights_pod.sh > /dev/null 2>&1 < /dev/null &      (from CB)
set -Euo pipefail
CB=${CB:-/workspace/cb_rt35}; PY=${PY:-/workspace/venv35/bin/python}; RT=${RT:-20261016-linux}
O=${O:-/workspace/results/FIGHTS35}; LIVE=${LIVE:-$CB/scratchpad/gauntlet/L68/live_reader}
W=${WORKERS:-$(( $(nproc) > 2 ? $(nproc) - 1 : 1 ))}
mkdir -p $O; exec >> $O/run.log 2>&1
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=$RT OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
echo "$(date -u +%T) start RT=$RT PY=$PY CB=$CB LIVE=$LIVE workers=$W files=$(ls $LIVE/live_play_2026101[5-9]_*.jsonl | wc -l)"
$PY -c "from pipeline.royale_runtime import activate; s = activate(); print(s['runtime_id'], s['pins'])" || { echo "RUNTIME FAILED"; touch $O/FAILED; exit 2; }
flock /workspace/cpu.lock $PY scratchpad/gauntlet/L74/parity/fights.py run --out $O --live $LIVE \
  --files 'live_play_2026101[5-9]_*.jsonl' --workers $W --window ${WINDOW:-240} || { echo "FIGHTS EXIT"; touch $O/FAILED; exit 2; }
touch $O/DONE
echo "$(date -u +%T) done"
