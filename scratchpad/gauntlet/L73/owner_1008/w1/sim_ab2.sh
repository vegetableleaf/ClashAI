#!/bin/bash
# W1 SIM A/B extension: --own-effects on seeds 240:480, merged with 0:240, paired vs the bench base g3_live_rocket (0:480; reproduced exactly on 0:240)
source ~/eval_vm.sh; O=~/eval_ns; LOG=~/w1/ab.log; W=16
CK=icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref.pt
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area)
for s in "" lad; do d=$EVO; [ "$s" = lad ] && d=$LAD
  ( $PY -m pipeline.search_s0 --out $O/react${s}_w1_ownfx_b --seeds 240:480 --opps gen --arms plain --gen $CK --opp-gen $GEN1 --forms-mode deck \
      --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census $d --hero-abilities --ability-policy v2 \
      --opp-policy sample --opp-T 0.3 "${LV[@]}" --own-effects > $O/react${s}_w1_ownfx_b.log 2>&1
    mkdir -p $O/react${s}_w1_ownfx480; cat $O/react${s}_w1_ownfx/matches.jsonl $O/react${s}_w1_ownfx_b/matches.jsonl > $O/react${s}_w1_ownfx480/matches.jsonl ) &
done; wait
~/venv/bin/python ~/paired.py g3_live_rocket w1_ownfx480 >> $LOG
echo "W1 AB2 DONE $(date "+%F %T")" >> $LOG
