#!/bin/bash
# usage: run_mech.sh MECH OUTDIR SEEDS WORKERS CENSUS(evo|lad) [CHECK]   (run from the mechanic's worktree; nice 10)
#   sneaky   -> /workspace/wt_fork_sl (branch a666a874 af50e7f1: --sneaky-lock)
#   patience -> /workspace/wt_fork_pt (branch a9182138 1727010: --patience E X)
# Benchmark flags = sim_val.sh + --behaviour-telemetry (the 960 A/B's own command line).
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
M=$1; O=$2; S=$3; W=$4; C=$5; K=${6:-0}
PY=/workspace/venv/bin/python
CK=icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt
GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
D=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json
[ "$C" = lad ] && D=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects
    --gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --log-aim log_barrel --lethal-rocket ot_behind
    --xbow-dead-lane block --gate-hazard-threatened 2 --rocket-dead-target block --tau-threatened 0.2 --lethal-log on
    --behaviour-telemetry)
MECH=$M MECH_CHECK=$K nice -n 10 $PY scratchpad/gauntlet/L74/mechanic_fork/mech_fork.py --out $O --seeds $S --opps gen \
  --arms plain --gen $CK --opp-gen $GEN1 --forms-mode deck --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 \
  --census $D --hero-abilities --ability-policy v2 --opp-policy sample --opp-T 0.3 "${LV[@]}"
