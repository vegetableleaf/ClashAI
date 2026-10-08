#!/bin/bash
# L73 centre-column: the 192-game reactive set (react + reactlad, eval_vm.sh flags) through sim_lane.py (search_s0
# unchanged + per-play lane log). Usage: cellref_sim.sh NAME CKPT
source ~/eval_vm.sh; O=~/eval_ns; LOG=$O/eval.log; W=${WORKERS:-12}
lane() {  # name ckpt suffix census
  CENTRE_LOG_DIR=$O/lane$3_$1 $PY scratchpad/gauntlet/L73/centre_col/sim_lane.py --out $O/react$3_$1 --seeds 0:48 --opps gen,s1 --arms plain --gen $2 --opp-gen $GEN1 --forms-mode deck \
      --device cpu --workers $W --tail-cap 7200 --tau-plain ${TAU:-0.35} --census $4 --hero-abilities --ability-policy v2 ${SIM_EXTRA:-} > $O/react$3_$1.log 2>&1
  log "react$3 $1 (sim_lane): gen $(nwin $O/react$3_$1.log gen)/48 s1 $(nwin $O/react$3_$1.log s1)/48"
}
lane $1 $2 "" $EVO & a=$!; lane $1 $2 lad $LAD & b=$!; wait $a $b
$PY scratchpad/gauntlet/L73/centre_col/sim_lane.py --summarise $O/lane_$1 $O/lanelad_$1 >> $O/lane_summary.txt
log "cellref_sim $1 DONE"
