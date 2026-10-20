#!/bin/bash
# W8 fin15 (P2), beside fin15_pod.sh: the single-process J-suite steps of run_metrics_pod.sh (elixir J4 with H-J4-CAPDATE, laws
# J5b / J8 with H-J8-CLASS) on the fin15 wheel into METRICS_J15, then scores METRICS_J15 + its whole/ once fin15_pod.sh is done.
#   S=rsfork_fin15 setsid nohup bash fin15_laws.sh > /dev/null 2>&1 < /dev/null &
set -uo pipefail
S=/workspace/${S:?}; C=/workspace/cb13; L=/workspace/caplogs13; M=/workspace/results/METRICS_J15; mkdir -p $M
cd $C
export PYTHONPATH=$C PARITY_SIM_PATH=$S OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
P=scratchpad/gauntlet/L74/parity
python3 $P/metrics/replay_metrics.py elixir --out $M --live $L --files 'live_play_*.jsonl' > $M/run_elixir.log 2>&1 || touch $M/FAILED_elixir
python3 $P/metrics/replay_metrics.py laws --out $M --live $L --files 'live_play_*.jsonl' > $M/run_laws.log 2>&1 || touch $M/FAILED_laws
touch $M/LAWS_DONE
while [ ! -e /workspace/w8/fin15_pod.DONE ]; do sleep 60; done
python3 $P/metrics/replay_metrics.py score --out $M > $M/SCORE_all.txt 2>&1
python3 $P/metrics/replay_metrics.py score --out $M/whole > $M/SCORE_whole.txt 2>&1
touch $M/DONE
