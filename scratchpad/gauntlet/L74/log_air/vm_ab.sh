#!/bin/bash
# --log-air SIM A/B (benchmark v3: GEN v1 opponent sampling T .3, seeds 0:240 per census): arms base / retarget / block x
# censuses evo (EVO) + lad (ladder) + air (the 122 air-heavy decks of the air-answer branch, air_census.json) = 3 x 720 games,
# 720 paired per arm pair. Code ~/log_air/repo (vm_setup.sh). Every arm = the deployed LIVE_OPTIONS decision flags (live-only flags
# left out), through log_fire_s0.py (logs every Log play and the log_air touches; logging only).
#   ARMS="base retarget" WORKERS=8 bash vm_ab.sh        (jobs = arms x 3 censuses, $WORKERS processes each, nice $NICE)
#   ARMS=block NICE=19 WORKERS=3 bash vm_ab.sh          (the comparison arm, lower priority)
cd ~/log_air/repo
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=~/venv/bin/python; O=~/log_air/sim; mkdir -p $O; W=${WORKERS:-3}; NICE=${NICE:-10}; ARMS=${ARMS:-"base retarget block"}; LOG=$O/sim_${ARMS// /_}.log; SEEDS=${SEEDS:-0:240}
CK=$HOME/lethal/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt; GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
declare -A CEN=([evo]=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json [lad]=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json
                [air]=scratchpad/gauntlet/L74/log_air/air_census.json)
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects
    --gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --log-aim log_barrel --lethal-rocket ot_behind --xbow-dead-lane block
    --gate-hazard-threatened 2)
declare -A X=([base]="" [retarget]="--log-air retarget" [block]="--log-air block")
run() { local arm=$1 s=$2
  export FIRE_DIR=$O/fires_${arm}_$s; mkdir -p $FIRE_DIR
  nice -n $NICE $PY scratchpad/gauntlet/L74/log_air/log_fire_s0.py --out $O/${arm}_$s --seeds $SEEDS --opps gen --arms plain \
    --gen $CK --opp-gen $GEN1 --forms-mode deck --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census ${CEN[$s]} \
    --hero-abilities --ability-policy v2 --opp-policy sample --opp-T 0.3 "${LV[@]}" ${X[$arm]} > $O/${arm}_$s.log 2>&1
  echo "$arm $s rc=$? $(date +%T)" >> $LOG; }
for a in $ARMS; do for s in evo lad air; do run $a $s & done; done
wait
echo DONE >> $LOG
