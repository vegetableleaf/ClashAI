#!/bin/bash
# W8: the 10-20 classic-challenge parity battles (40 logs with phase-3 captures; caplogs20) on fin14c (before) and fin15 (after):
# J1 (fights.py, K = 8) + the J-suite, as fin15_pod.sh / fin15_laws.sh. Code tree cb20 = cb13 + MinionGiant in the harness catalog (the Hero Electro
# Wizard form NOT added: the fork cannot load it, "ElectroWizard has no loadable hero form"). PARITY_ANY_DECK=1: the bot plays the
# rare-card decks here, not icebow. Waits for the 638-log fin15 runs (one CPU job on the pod).
#   setsid nohup bash run20.sh > /dev/null 2>&1 < /dev/null &
set -uo pipefail
while [ ! -e ${WAIT:-/workspace/results/METRICS_J15/DONE} ]; do sleep 60; done
C=${C:-/workspace/cb20}; L=/workspace/caplogs20; W=${WORKERS:-24}; K=8; exec >> /workspace/w8/run20${TAG:-}.log 2>&1
cd $C
export PARITY_ANY_DECK=1 PYTHONPATH=$C PARITY_BUFFS=/workspace/w8/in20/buffs20.json PARITY_ATTACKS=/workspace/w8/in20/attacks20.json \
  OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
P=scratchpad/gauntlet/L74/parity
for S in ${SIMS:-rsfork_fin15 rsfork_fin14c}; do
  export PARITY_SIM_PATH=/workspace/$S; T=${S#rsfork_}
  O=/workspace/results/FIN_20_$T; M=/workspace/results/METRICS_20_$T; mkdir -p $O $M
  echo "$(date -u +%T) $S start"
  nice -n 5 python3 $P/fights.py run --out $O --live $L --files 'live_play_*.jsonl' --workers $W --window 240 --ceiling $K > $O/run.log 2>&1
  python3 $P/fights.py score --out $O > $O/score.log 2>&1
  nice -n 5 python3 $P/metrics/replay_metrics.py fights --out $M --live $L --files 'live_play_*.jsonl' --ceiling $K --workers $W > $M/run_fights.log 2>&1
  nice -n 5 python3 $P/metrics/replay_metrics.py whole --out $M/whole --live $L --files 'live_play_*.jsonl' --ceiling $K --workers $W > $M/run_whole.log 2>&1
  python3 $P/metrics/replay_metrics.py elixir --out $M --live $L --files 'live_play_*.jsonl' > $M/run_elixir.log 2>&1
  python3 $P/metrics/replay_metrics.py laws --out $M --live $L --files 'live_play_*.jsonl' > $M/run_laws.log 2>&1
  python3 $P/metrics/replay_metrics.py score --out $M > $M/SCORE_all.txt 2>&1
  python3 $P/metrics/replay_metrics.py score --out $M/whole > $M/SCORE_whole.txt 2>&1
  python3 $P/metrics/percard.py $M 1 > $M/PERCARD.md 2>&1
  echo "$(date -u +%T) $S done"
done
touch /workspace/w8/run20${TAG:-}.DONE
