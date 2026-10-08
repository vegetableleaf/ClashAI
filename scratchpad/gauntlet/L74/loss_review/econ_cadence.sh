#!/bin/bash
# L74 cadence test (lead 10-08): deployed live options at main 049772e on the live checkpoint (towerref_w2, sha 41b52a83),
# learner decides every 10 ticks (control, = SIM default) vs every 4 ticks (live-like hypothesis). Opponent cadence unchanged.
# Isolated ~/loss_review/repo49 = git archive 049772e pipeline + econ_sim_patch.py. --iw-press-pstar omitted (SIM has no Hero Ice Wizard).
# v3 benchmark as W4 (vs gen v1 sampling T .3), seeds 0:240 x evo + lad = 480 paired matches per arm. CPU, nice.
cd ~/loss_review/repo49
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=~/venv/bin/python; O=~/loss_review/sim49; W=${WORKERS:-12}; LOG=$O/sim.log; mkdir -p $O
CK=/home/clashbot-gauntlet/probe_rocket/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt
GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
EVO=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json; LAD=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects
    --gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --log-aim log_barrel --lethal-rocket ot)
SEEDS=${SEEDS:-0:240}
run() { local name=$1
  for s in evo lad; do d=$EVO; [ $s = lad ] && d=$LAD
    nice $PY -m pipeline.search_s0 --out $O/${name}_$s --seeds $SEEDS --opps gen --arms plain --gen $CK --opp-gen $GEN1 \
      --forms-mode deck --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census $d --hero-abilities \
      --ability-policy v2 --behaviour-telemetry --opp-policy sample --opp-T 0.3 "${LV[@]}" > $O/${name}_$s.log 2>&1
    echo "$name $s rc=$? $(date +%T)" >> $LOG; done; }
LR_DECIDE_EVERY=10 run de10
LR_DECIDE_EVERY=4 run de4
echo DONE >> $LOG
