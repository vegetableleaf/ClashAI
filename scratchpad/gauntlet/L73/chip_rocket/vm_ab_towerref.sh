#!/bin/bash
# TowerRefine SIM A/B (benchmark v3: GEN opponent, sample T .3), live options + rocket_area + behaviour telemetry.
# Arms: base = live checkpoint; w1 / w2 = base + TowerRefine (folded). Seeds 0:240 x census + ladder = 480 paired games/arm.
source ~/eval_vm.sh; O=~/probe_rocket; LOG=$O/ab.log; W=${WORKERS:-16}
CK=icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref.pt
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --behaviour-telemetry)
g() { local n=$1 ck=$2
  for s in "" lad; do d=$EVO; [ "$s" = lad ] && d=$LAD
    $PY -m pipeline.search_s0 --out $O/react${s}_$n --seeds 0:240 --opps gen --arms plain --gen $ck --opp-gen $GEN1 --forms-mode deck \
      --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census $d --hero-abilities --ability-policy v2 \
      --opp-policy sample --opp-T 0.3 "${LV[@]}" > $O/react${s}_$n.log 2>&1
    log "react$s $n: gen $(nwin $O/react${s}_$n.log gen)/240"; done; }
g tr_base $CK
g tr_w1 $O/rseries_r3c_u0030_barrel2k_cellref_towerref_w1.pt
g tr_w2 $O/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt
log "AB DONE"
