#!/bin/bash
# lethal_log release v4 (baseline at/after landing) on tree ~/lethal/rel_v4; arms v4_on / v4_off into ~/lethal/sim_rel next to main_* (sim_rel.sh).
# Trees: ~/lethal/rel_main (pipeline @ 9eb8e34) and ~/lethal/rel_br (branch lethal-log-release); the same committed
# fire_log_s0.py (logging only) in both. Deployed LIVE_OPTIONS decision bundle (SIM-accepted flags; live-only input /
# reader flags are not SIM options); arms: main_on, br_on (--lethal-log on), main_off, br_off (--lethal-log off).
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=~/venv/bin/python; O=~/lethal/sim_rel; W=${WORKERS:-5}; LOG=$O/sim_v4.log; mkdir -p $O
CK=$HOME/lethal/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt; GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
EVO=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json; LAD=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects
    --gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --log-aim log_barrel --lethal-rocket ot_behind
    --xbow-dead-lane block --gate-hazard-threatened 2 --rocket-dead-target block --tau-threatened 0.2)
run() { local tree=$1 lg=$2 s=$3 arm=${1}_${2}; d=$EVO; [ $s = lad ] && d=$LAD
  export FIRE_DIR=$O/fires_${arm}_$s; mkdir -p $FIRE_DIR
  (cd ~/lethal/rel_$tree && nice -n 10 $PY ~/lethal/fire_log_s0_rel.py --out $O/v3_${arm}_$s --seeds 0:240 --opps gen \
    --arms plain --gen $CK --opp-gen $GEN1 --forms-mode deck --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 \
    --census $d --hero-abilities --ability-policy v2 --behaviour-telemetry --opp-policy sample --opp-T 0.3 "${LV[@]}" \
    --lethal-log $lg > $O/v3_${arm}_$s.log 2>&1)
  echo "$arm $s rc=$? $(date +%T)" >> $LOG; }
for s in evo lad; do for t in v4; do for lg in on off; do run $t $lg $s & done; done; done
wait
echo DONE >> $LOG
