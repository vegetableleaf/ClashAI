#!/bin/bash
# W1 SIM A/B: benchmark v3 (gen opp sampling T .3), seeds 0:240 x census + ladder, live options + rocket_area; base vs --own-effects
source ~/eval_vm.sh; O=~/eval_ns; LOG=~/w1/ab.log; W=16
CK=icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref.pt
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area)
g() { local n=$1; shift
  for s in "" lad; do d=$EVO; [ "$s" = lad ] && d=$LAD
    $PY -m pipeline.search_s0 --out $O/react${s}_$n --seeds 0:240 --opps gen --arms plain --gen $CK --opp-gen $GEN1 --forms-mode deck \
      --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census $d --hero-abilities --ability-policy v2 \
      --opp-policy sample --opp-T 0.3 "${LV[@]}" "$@" > $O/react${s}_$n.log 2>&1
    echo "react$s $n: gen $(nwin $O/react${s}_$n.log gen)/240 $(date "+%F %T")" >> $LOG; done; }
g w1_base &
g w1_ownfx --own-effects &
wait
~/venv/bin/python ~/paired.py w1_base w1_ownfx >> $LOG
~/venv/bin/python ~/paired.py g3_live_rocket w1_base >> $LOG
echo "W1 AB DONE $(date "+%F %T")" >> $LOG
