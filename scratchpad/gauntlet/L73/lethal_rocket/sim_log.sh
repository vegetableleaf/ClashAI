#!/bin/bash
# lethal_log SIM A/B (tree ~/lethal/logt = branch lethal-log). v3, seeds 0:240 x census + ladder = 480 paired. Deployed LIVE_OPTIONS decision bundle (live-only input flags and --iw-press-pstar are not SIM options;
# the SIM presses abilities with --ability-policy v2): arms off / on = --lethal-log (both --lethal-rocket ot_behind --xbow-dead-lane block).
# Both arms run through fire_log_s0.py so every rule fire is logged (FIRE_DIR); outcomes are unaffected (logging only).
cd ~/lethal/logt
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=~/venv/bin/python; O=~/lethal/sim_log; W=${WORKERS:-16}; LOG=$O/sim.log; mkdir -p $O
CK=$HOME/lethal/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt; GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
EVO=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json; LAD=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects
    --gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --log-aim log_barrel)
run() { local arm=$1 s=$2; d=$EVO; [ $s = lad ] && d=$LAD
  export FIRE_DIR=$O/fires_${arm}_$s; mkdir -p $FIRE_DIR
  nice -n 10 $PY scratchpad/gauntlet/L73/lethal_rocket/fire_log_s0.py --out $O/v3_${arm}_$s --seeds 0:240 --opps gen --arms plain \
    --gen $CK --opp-gen $GEN1 --forms-mode deck --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census $d \
    --hero-abilities --ability-policy v2 --behaviour-telemetry --opp-policy sample --opp-T 0.3 "${LV[@]}" \
    --lethal-rocket ot_behind --lethal-log $arm --xbow-dead-lane block > $O/v3_${arm}_$s.log 2>&1
  echo "$arm $s rc=$? $(date +%T)" >> $LOG; }
for s in evo lad; do run off $s & run on $s & done
wait
echo DONE >> $LOG
