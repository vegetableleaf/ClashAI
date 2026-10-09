#!/bin/bash
# --gate-hazard-threatened SIM A/B (benchmark v3: GEN v1 opponent sampling T .3, seeds 0:480 x census EVO + ladder
# LAD = 960 paired). Code: ~/threat/repo (vm_setup.sh). Every arm = the DEPLOYED LIVE_OPTIONS (main 808f4f4) minus the
# live-only flags (--iw-press-pstar, --fast-input, --tap-gap-ms; --afford-ticks / --extrapolate 24 are not search_s0
# flags: its live condition is delay 26 / extrapolate 26), checkpoint towerref_w2 41b52a83.
#   thr = + --gate-hazard-threatened 2 ; rad = + --gate-hazard-threat-radius 4 (the variant)
#   ARMS="base thr rad" SEEDS=0:480 WORKERS=32 bash vm_ab.sh
cd ~/threat/repo
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES=
PY=~/venv/bin/python; O=~/threat/sim${TAG:-}; mkdir -p $O; W=${WORKERS:-32}; LOG=$O/sim.log; SEEDS=${SEEDS:-0:480}
CK=$HOME/lethal/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt; GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
EVO=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json; LAD=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects
    --gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --log-aim log_barrel --lethal-rocket ot_behind
    --xbow-dead-lane block --behaviour-telemetry)
declare -A X=([base]="" [thr]="--gate-hazard-threatened 2" [rad]="--gate-hazard-threat-radius 4")
run() { local name=$1
  for s in evo lad; do d=$EVO; [ $s = lad ] && d=$LAD
    nice $PY -m pipeline.search_s0 --out $O/${name}_$s --seeds $SEEDS --opps gen --arms plain --gen $CK --opp-gen $GEN1 \
      --forms-mode deck --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census $d --hero-abilities \
      --ability-policy v2 --opp-policy sample --opp-T 0.3 "${LV[@]}" ${X[$name]} > $O/${name}_$s.log 2>&1
    echo "$name $s rc=$? $(date +%T)" >> $LOG; done; }
for a in ${ARMS:-base thr rad}; do run $a & done
wait
echo DONE >> $LOG
