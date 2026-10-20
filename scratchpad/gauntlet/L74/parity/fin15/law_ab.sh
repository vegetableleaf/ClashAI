#!/bin/bash
# W8 law A/B on one fin15 wheel (P2): arm A = the wheel's shipped arms, arm B = PARITY_OVERRIDES=$OVR. K = 0 (no ceiling) for
# speed; both arms run the same 638 caplogs13 logs, so the A/B is like for like (aK falls back to a0 at K = 0).
#   S=rsfork_fin15b TAG=torn OVR='{"collision.ATTRACT_CONTACT_MEAN": "client16402_in_mean_uncapped"}' [J1=1] bash law_ab.sh
# -> /workspace/w8/ab_$TAG/{A,B}/{metrics (J2/J3/J6/J5a: SCORE.txt), j1 (fights.py, SCOREBOARD)}, DONE
set -uo pipefail
S=${S:?}; TAG=${TAG:?}; OVR=${OVR:?}; W=${WORKERS:-22}
O=/workspace/w8/ab_$TAG; mkdir -p $O; exec >> $O/run.log 2>&1
cd /workspace/cb13
export PYTHONPATH=/workspace/cb13 PARITY_SIM_PATH=/workspace/$S PARITY_BUFFS=/workspace/in13/buffs13.json PARITY_ATTACKS=/workspace/in13/attacks13s.json \
  OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
P=scratchpad/gauntlet/L74/parity
for arm in A B; do
  if [ $arm = B ]; then export PARITY_OVERRIDES="$OVR"; else unset PARITY_OVERRIDES; fi
  mkdir -p $O/$arm; echo "$(date -u +%T) arm $arm overrides=${PARITY_OVERRIDES:-none}"
  nice -n 5 python3 $P/metrics/replay_metrics.py fights --out $O/$arm/metrics --live /workspace/caplogs13 --files 'live_play_*.jsonl' --ceiling 0 --workers $W > $O/$arm/metrics.log 2>&1 \
    || mkdir -p $O/$arm/metrics
  python3 $P/metrics/replay_metrics.py score --out $O/$arm/metrics > $O/$arm/metrics_score.txt 2>&1
  if [ "${J1:-0}" = 1 ]; then
    nice -n 5 python3 $P/fights.py run --out $O/$arm/j1 --live /workspace/caplogs13 --files 'live_play_*.jsonl' --workers $W --window 240 --ceiling 0 > $O/$arm/j1.log 2>&1
    python3 $P/fights.py score --out $O/$arm/j1 --stamped > $O/$arm/j1_score_stamped.txt 2>&1
  fi
done
echo "$(date -u +%T) done"; touch $O/DONE
