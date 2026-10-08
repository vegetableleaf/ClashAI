#!/bin/bash
# L73 barrel-heavy benchmark v2: gen opponents only (S1 always plays icebow), every opp deck has Goblin Barrel.
# Usage: barrel_sim.sh NAME CKPT   (seeds 0:96 -> 96 games)
source ~/eval_vm.sh; O=~/eval_ns; LOG=$O/eval.log; W=${WORKERS:-16}
CENTRE_LOG_DIR=$O/lanegb_$1 $PY scratchpad/gauntlet/L73/centre_col/sim_lane.py --out $O/reactgb_$1 --seeds ${SEEDS:-0:96} --opps gen --arms plain --gen $2 --opp-gen $GEN1 --forms-mode deck \
    --device cpu --workers $W --tail-cap 7200 --tau-plain ${TAU:-0.35} --census scratchpad/gauntlet/L73/centre_col/barrel_census.json --hero-abilities --ability-policy v2 --opp-policy sample --opp-T 0.3 > $O/reactgb_$1.log 2>&1
$PY scratchpad/gauntlet/L73/centre_col/sim_lane.py --summarise $O/lanegb_$1 >> $O/lane_summary.txt
log "barrel_sim $1: gen $(nwin $O/reactgb_$1.log gen)/96 DONE"
