#!/bin/bash
# J-suite engine metrics on the FIN13 cohort (METRICS.md section 6): the patched fork runtime (rsfork_fin14c, clashbot36
# 427597d3), every captured log, K = 8. NOT RUN by W1 (pods busy until ~06:00 EDT 10-20; the lead schedules it).
# Inputs as fin13_pod.sh (diag_night/r7_closer): $C = a code checkout at HEAD with parity/metrics/ synced, $L = caplogs13,
# PARITY_BUFFS / PARITY_ATTACKS exports. Results: $O/{census.json, matches/ (J2/J3/J6), whole/matches/ (J7), elixir/, laws/,
# SCORE*.txt, DONE}. Laptop-measured costs (0.1.36, one process): fights ~20 s / match at K=4, whole ~3 s per replay.
#   nohup bash scratchpad/gauntlet/L74/parity/metrics/run_metrics_pod.sh > /dev/null 2>&1 < /dev/null &     (from $C)
set -Euo pipefail
S=${S:-/workspace/rsfork_fin14c}; C=${C:-/workspace/cb13}; L=${L:-/workspace/caplogs13}; O=${O:-/workspace/results/METRICS_J}
K=${CEILING:-8}; W=${WORKERS:-$(( $(nproc) > 2 ? $(nproc) - 1 : 1 ))}
mkdir -p $O; exec >> $O/run.log 2>&1
cd $C
export PYTHONPATH=$C PARITY_SIM_PATH=$S PARITY_BUFFS=${PARITY_BUFFS:-/workspace/in/buffs13.json} \
  PARITY_ATTACKS=${PARITY_ATTACKS:-/workspace/in/attacks13s.json} OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
M=scratchpad/gauntlet/L74/parity/metrics
echo "$(date -u +%T) start SIM=$S CODE=$C logs=$(ls $L | wc -l) K=$K workers=$W"
[ "${SKIP_SELFTEST:-0}" = 1 ] || python3 $M/test_metrics.py || { touch $O/FAILED; exit 2; }   # SKIP_SELFTEST=1: pod trees without pipeline/ (cb13); the selftest passes on the laptop
python3 $M/replay_metrics.py fights --out $O --live $L --files 'live_play_*.jsonl' --ceiling $K --workers $W || touch $O/FAILED_fights
python3 $M/replay_metrics.py whole --out $O/whole --live $L --files 'live_play_2026101[789]_*.jsonl' --ceiling $K --workers $W || touch $O/FAILED_whole
python3 $M/replay_metrics.py elixir --out $O --live $L --files 'live_play_*.jsonl' || touch $O/FAILED_elixir
python3 $M/replay_metrics.py laws --out $O --live $L --files 'live_play_*.jsonl' || touch $O/FAILED_laws
python3 $M/replay_metrics.py score --out $O > $O/SCORE_all.txt 2>&1
python3 $M/replay_metrics.py score --out $O/whole > $O/SCORE_whole.txt 2>&1
mkdir -p $O/fin13 && python3 $M/replay_metrics.py score --out /workspace/results/FIN13 --to $O/fin13 > $O/SCORE_fin13_deploy.txt 2>&1 || true   # J5a from FIN13 bodies (read only)
touch $O/DONE
echo "$(date -u +%T) done"
