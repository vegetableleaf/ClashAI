#!/bin/bash
# lethal_rocket SIM A/B (isolated tree ~/lethal/mine = this branch: W4 + lethal_rocket; never ~/ClashBot).
# v3 benchmark as W4 (L73/w4_gate/sim_w4.sh): vs gen v1 sampling T .3, seeds 0:480 x census (EVO) + ladder (LAD) = 960
# paired games per arm. Checkpoint = the LIVE one (towerref_w2, sha 41b52a83). Arms: base = live options; lr = + --lethal-rocket ot.
cd ~/lethal/mine
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=~/venv/bin/python; O=~/lethal/sim; W=${WORKERS:-16}; LOG=$O/sim.log; mkdir -p $O
CK=$HOME/lethal/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt; GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
EVO=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json; LAD=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects)
run() { local name=$1 s=$2; shift 2; d=$EVO; [ $s = lad ] && d=$LAD
  nice $PY -m pipeline.search_s0 --out $O/${name}_$s --seeds 0:480 --opps gen --arms plain --gen $CK --opp-gen $GEN1 \
    --forms-mode deck --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census $d --hero-abilities \
    --ability-policy v2 --behaviour-telemetry --opp-policy sample --opp-T 0.3 "${LV[@]}" "$@" > $O/${name}_$s.log 2>&1
  echo "$name $s rc=$? $(date +%T)" >> $LOG; }
for s in evo lad; do
  run v3_base $s &
  run v3_lr $s --lethal-rocket ot &
  wait
done
echo DONE >> $LOG
