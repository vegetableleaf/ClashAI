#!/bin/bash
# usage: run_wk.sh MECH OUTDIR SEEDS WORKERS CENSUS(evo|lad) CHECK CKPT [dump]     (run from the l74-weekend worktree; nice 10)
# MECH prevent | drills (mech_fork.py) or "dump" (sim_dump.py: the S9 pass-1 state dump into $DUMP_DIR).  Env passed through: ROWS_DIR, MOMENTS, MECH_GAP, MECH_MAXFORK.
# Flags = run_mech.sh (the E4 evals' live flags + --behaviour-telemetry).  CKPT is relative to the repo.
export ROYALE_RUNTIME=${ROYALE_RUNTIME:-20261006-linux} OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
M=$1; O=$2; S=$3; W=$4; C=$5; K=${6:-0}; CK=$7
PY=${PY:-/workspace/venv/bin/python}
GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
D=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json
[ "$C" = lad ] && D=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects
    --gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --log-aim log_barrel --lethal-rocket ot_behind
    --xbow-dead-lane block --gate-hazard-threatened 2 --rocket-dead-target block --tau-threatened 0.2 --lethal-log on
    --behaviour-telemetry)
[ -n "$CENSUS_FILE" ] && D=$CENSUS_FILE      # S9: the archetype-weighted copy
SCRIPT=scratchpad/gauntlet/L74/mechanic_fork/mech_fork.py
[ "$M" = logbait ] && SCRIPT=scratchpad/gauntlet/L74/weekend/logbait_s0.py
[ "$M" = dump ] && SCRIPT=scratchpad/gauntlet/L74/drills/sim_dump.py
CB_MAIN=$PWD MECH=$M MECH_CHECK=$K nice -n 10 $PY $SCRIPT --out $O --seeds $S --opps gen \
  --arms plain --gen $CK --opp-gen $GEN1 --forms-mode deck --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 \
  --census $D --hero-abilities --ability-policy v2 --opp-policy sample --opp-T 0.3 "${LV[@]}"
