#!/bin/bash
# W8 fin15 (P2): FIN15 = the HEAD harness (cb13 + the W8 replay_metrics.py) on the final fin15 wheel, as fin13_pod.sh, then the J-suite
# (metrics/run_metrics_pod.sh's fights + whole steps; elixir + laws run beside it in fin15_laws.sh) into METRICS_J15, and J5a from
# the FIN15 bodies.
#   S=rsfork_fin15 WORKERS=24 setsid nohup bash fin15_pod.sh > /dev/null 2>&1 < /dev/null &
# -> /workspace/results/{FIN15, FIN15_stamped, METRICS_J15}/..., /workspace/w8/fin15_pod.DONE
set -uo pipefail
S=/workspace/${S:?}; C=${C:-/workspace/cb13}; L=/workspace/caplogs13; W=${WORKERS:-24}; K=${CEILING:-8}
O=${O:-/workspace/results/FIN15}; M=${M:-/workspace/results/METRICS_J15}; TAG=${TAG:-fin15}; mkdir -p $O $M; exec >> /workspace/w8/${TAG}_pod.log 2>&1
cd $C
export PYTHONPATH=$C PARITY_SIM_PATH=$S PARITY_BUFFS=/workspace/in13/buffs13.json PARITY_ATTACKS=/workspace/in13/attacks13s.json \
  OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
P=scratchpad/gauntlet/L74/parity
echo "$(date -u +%T) FIN15 start SIM=$S files=$(ls $L | wc -l) K=$K workers=$W"
if [ ! -e $O/DONE ]; then
  nice -n 5 python3 $P/fights.py run --out $O --live $L --files 'live_play_*.jsonl' --workers $W --window 240 --ceiling $K > $O/run.log 2>&1 && touch $O/DONE || touch $O/FAILED
fi
echo "$(date -u +%T) FIN15 run end"
if [ -e $O/DONE ] && [ ! -e ${O}_stamped/DONE ]; then
  rm -rf ${O}_stamped; cp -al $O ${O}_stamped
  rm -f ${O}_stamped/CEILING_* ${O}_stamped/SCOREBOARD_* ${O}_stamped/ceiling_*.json ${O}_stamped/scoreboard_*.json ${O}_stamped/DONE
  python3 $P/fights.py score --out ${O}_stamped --stamped > ${O}_stamped/score.log 2>&1 && touch ${O}_stamped/DONE || touch ${O}_stamped/FAILED
fi
echo "$(date -u +%T) FIN15 stamped end; J-suite start"
# run_metrics_pod.sh's fights + whole (the parallel single-process job fin15_laws.sh does its elixir + laws, so the pod runs one
# CPU job of W + 1 processes); score once both are done (fin15_score.sh)
python3 $P/metrics/replay_metrics.py fights --out $M --live $L --files 'live_play_*.jsonl' --ceiling $K --workers $W > $M/run_fights.log 2>&1 || touch $M/FAILED_fights
python3 $P/metrics/replay_metrics.py whole --out $M/whole --live $L --files 'live_play_2026101[789]_*.jsonl' --ceiling $K --workers $W > $M/run_whole.log 2>&1 || touch $M/FAILED_whole
mkdir -p $M/fin15; python3 $P/metrics/replay_metrics.py score --out $O --to $M/fin15 > $M/SCORE_fin15_deploy.txt 2>&1 || true   # J5a from the FIN15 bodies
echo "$(date -u +%T) done"; touch /workspace/w8/${TAG}_pod.DONE
