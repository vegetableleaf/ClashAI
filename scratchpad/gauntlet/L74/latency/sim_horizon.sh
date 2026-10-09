#!/bin/bash
# L74 horizon SIM A/B (isolated tree ~/afford/mine = branch l74-afford-arrival + horizon_sim_patch.py; never ~/ClashBot).
# v3 benchmark as the lethal-rocket A/B: vs gen v1 sampling T .3, seeds 0:480 x census (EVO) + ladder (LAD) = 960 paired
# games per arm, the LIVE checkpoint (towerref_w2, sha 41b52a83) with the deployed LIVE_OPTIONS bundle
# (--iw-press-pstar omitted: the SIM has no Hero Ice Wizard pro gate). Learner-only arms (opponent stays 26/26):
#   d26  = delay 26, extrapolate 26 (today)      d24 = delay 24, extrapolate 24      d24a23 = d24 + afford_ticks 23
cd ~/afford/mine
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=~/venv/bin/python; O=~/afford/sim; W=${WORKERS:-16}; LOG=$O/sim.log; mkdir -p $O
CK=$HOME/lethal/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt; GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
EVO=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json; LAD=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects
    --gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --log-aim log_barrel --lethal-rocket ot)
run() { local name=$1 s=$2 d=$EVO; [ $s = lad ] && d=$LAD
  nice $PY -m pipeline.search_s0 --out $O/${name}_$s --seeds 0:480 --opps gen --arms plain --gen $CK --opp-gen $GEN1 \
    --forms-mode deck --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census $d --hero-abilities \
    --ability-policy v2 --behaviour-telemetry --opp-policy sample --opp-T 0.3 "${LV[@]}" > $O/${name}_$s.log 2>&1
  echo "$name $s rc=$? $(date +%T)" >> $LOG; }
for s in evo lad; do
  LR_DELAY=26 LR_EXTRAP=26 run d26 $s &
  LR_DELAY=24 LR_EXTRAP=24 run d24 $s &
  LR_DELAY=24 LR_EXTRAP=24 LR_AFFORD=23 run d24a23 $s &
done
wait
echo DONE >> $LOG
