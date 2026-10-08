#!/bin/bash
# --xbow-dead-lane SIM A/B (benchmark v3: GEN v1 opponent sampling T .3, seeds 0:480 x census EVO + ladder LAD = 960
# paired). Code: ~/deadlane/repo = this branch's tar over symlinks to ~/ClashBot data (vm_setup.sh) + the push-Rocket
# telemetry + vm_tel_patch.py (measurement only). Both arms = the deployed LIVE_OPTIONS bundle on main 0a777d5
# (towerref_w2 41b52a83; --iw-press-pstar is live-only); block adds --xbow-dead-lane block.
#   ARMS="base block" SEEDS=0:480 WORKERS=32 bash vm_ab.sh
cd ~/deadlane/repo
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=~/venv/bin/python; O=~/deadlane/sim${TAG:-}; mkdir -p $O; W=${WORKERS:-32}; LOG=$O/sim.log; SEEDS=${SEEDS:-0:480}
CK=$HOME/lethal/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt; GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
EVO=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json; LAD=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects
    --gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --log-aim log_barrel --lethal-rocket ot --behaviour-telemetry)
declare -A X=([base]="" [block]="--xbow-dead-lane block")
run() { local name=$1
  for s in evo lad; do d=$EVO; [ $s = lad ] && d=$LAD
    nice $PY -m pipeline.search_s0 --out $O/${name}_$s --seeds $SEEDS --opps gen --arms plain --gen $CK --opp-gen $GEN1 \
      --forms-mode deck --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census $d --hero-abilities \
      --ability-policy v2 --opp-policy sample --opp-T 0.3 "${LV[@]}" ${X[$name]} > $O/${name}_$s.log 2>&1
    echo "$name $s rc=$? $(date +%T)" >> $LOG; done; }
for a in ${ARMS:-base block}; do run $a & done
wait
echo DONE >> $LOG
