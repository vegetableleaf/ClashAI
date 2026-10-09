#!/bin/bash
# More base games on new seeds (the VM gives a nice-10 job ~1 % of a core: throughput scales with the process count).
#   SEEDS=240:480 WORKERS=10 bash vm_base_more.sh     -> sim/base_{evo,lad,air}_b9  (summary and stage_b read base_*_b* too)
cd ~/log_air/repo
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=~/venv/bin/python; O=~/log_air/sim; W=${WORKERS:-10}; SEEDS=${SEEDS:-240:480}
CK=$HOME/lethal/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt; GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
declare -A CEN=([evo]=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json [lad]=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json
                [air]=scratchpad/gauntlet/L74/log_air/air_census.json)
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects
    --gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --log-aim log_barrel --lethal-rocket ot_behind --xbow-dead-lane block
    --gate-hazard-threatened 2)
for s in evo lad air; do
  export FIRE_DIR=$O/fires_base_${s}_b9; mkdir -p $FIRE_DIR
  nice -n 10 $PY scratchpad/gauntlet/L74/log_air/log_fire_s0.py --out $O/base_${s}_b9 --seeds $SEEDS --opps gen --arms plain \
    --gen $CK --opp-gen $GEN1 --forms-mode deck --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census ${CEN[$s]} \
    --hero-abilities --ability-policy v2 --opp-policy sample --opp-T 0.3 "${LV[@]}" > $O/base_${s}_b9.log 2>&1 &
done
wait
echo MORE_DONE >> $O/sim_base_more.log
