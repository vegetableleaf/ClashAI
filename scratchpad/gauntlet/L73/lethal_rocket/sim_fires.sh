#!/bin/bash
# Re-run the lethal_rocket arm through fire_log_s0.py (same seeds/flags as sim_lethal.sh) to log every rule fire.
cd ~/lethal/mine
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=~/venv/bin/python; O=~/lethal/sim; W=${WORKERS:-16}; LOG=$O/sim.log
CK=$HOME/lethal/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt; GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
EVO=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json; LAD=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects)
for s in evo lad; do d=$EVO; [ $s = lad ] && d=$LAD
  export FIRE_DIR=$O/fires_$s; mkdir -p $FIRE_DIR
  nice $PY scratchpad/gauntlet/L73/lethal_rocket/fire_log_s0.py --out $O/v3_lrlog_$s --seeds 0:480 --opps gen --arms plain \
    --gen $CK --opp-gen $GEN1 --forms-mode deck --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census $d \
    --hero-abilities --ability-policy v2 --behaviour-telemetry --opp-policy sample --opp-T 0.3 "${LV[@]}" \
    --lethal-rocket ot > $O/v3_lrlog_$s.log 2>&1 &
done
wait
echo "lrlog done $(date +%T)" >> $LOG
