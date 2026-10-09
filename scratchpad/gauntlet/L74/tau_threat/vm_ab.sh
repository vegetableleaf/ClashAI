#!/bin/bash
# --tau-threatened SIM A/B (benchmark v3 as rocket_dead/lethal: GEN v1 opponent sampling T .3, census EVO + ladder LAD, seeds
# 0:240 each = 480 paired per arm). Code ~/tau_threat/repo (vm_setup.sh). Every arm = the deployed LIVE_OPTIONS decision flags
# (SIM-capable ones; live-only flags left out) + --behaviour-telemetry (tau_tel.py hook); x10..x25 add --tau-threatened X.
#   ARMS="base x10 x15 x20 x25" SEEDS=0:240 WORKERS=2 TAG=_a bash vm_ab.sh        (all arms x both censuses run concurrently)
cd ~/tau_threat/repo
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=~/venv/bin/python; O=~/tau_threat/sim${TAG:-}; mkdir -p $O; W=${WORKERS:-2}; LOG=$O/sim.log; SEEDS=${SEEDS:-0:240}
CK=$HOME/lethal/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt; GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
EVO=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json; LAD=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects
    --gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --gate-hazard-threatened 2 --log-aim log_barrel
    --lethal-rocket ot_behind --xbow-dead-lane block --behaviour-telemetry)
declare -A X=([base]="" [x10]="--tau-threatened 0.10" [x15]="--tau-threatened 0.15" [x20]="--tau-threatened 0.20" [x25]="--tau-threatened 0.25")
run() { local name=$1 s=$2 d=$EVO; [ $s = lad ] && d=$LAD
  nice $PY -m pipeline.search_s0 --out $O/${name}_$s --seeds $SEEDS --opps gen --arms plain --gen $CK --opp-gen $GEN1 \
    --forms-mode deck --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census $d --hero-abilities \
    --ability-policy v2 --opp-policy sample --opp-T 0.3 "${LV[@]}" ${X[$name]} > $O/${name}_$s.log 2>&1
  echo "$name $s rc=$? $(date +%T)" >> $LOG; }
for a in ${ARMS:-base x10 x15 x20 x25}; do for s in evo lad; do run $a $s & done; done
wait
echo DONE >> $LOG
