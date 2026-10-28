#!/usr/bin/env bash
# LOOP-MEM: the identity harness split over P processes (production's Python memory is ~0.5 ms+ per row, so one process
# runs ~2 matches / 8 min). Census pairs 0..N-1 dealt round-robin; then mem_merge.py sums the per-process JSONs.
# usage (pod 32657): mem_par.sh OUTDIR [N=56] [P=8] [obs_id.py args ...]
#   env as run.sh (OBSID_RL, OBSID_CLXIII, OBSID_BUILD); each part compiles its own build dir; MEM_CPU0 = first core.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$1; N=${2:-56}; P=${3:-8}; C0=${MEM_CPU0:-0}; shift 3 || shift $#
mkdir -p "$OUT"
for ((p = 0; p < P; p++)); do
  pairs=$(seq -s, $p $P $((N - 1)))
  OBSID_BUILD="$OUT/build$p" taskset -c $((C0 + p * 4))-$((C0 + p * 4 + 3)) "$HERE/run.sh" "$OUT/part$p.json" --pairs "$pairs" --min-rows 0 --threads 2 "$@" \
    > "$OUT/part$p.log" 2>&1 &

done
wait
/workspace/venvf16/bin/python -I "$HERE/mem_merge.py" "$OUT" > "$OUT/merged.txt"
cat "$OUT/merged.txt"
