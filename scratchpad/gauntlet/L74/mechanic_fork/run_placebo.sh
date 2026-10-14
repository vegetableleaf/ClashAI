#!/bin/bash
# usage (cwd = worktree root): bash run_placebo.sh MECH OUTDIR SEEDS WORKERS CHECK   -- laptop; then lower the PID's priority (run_placebo prints it)
export ROYALE_RUNTIME=20261006 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 MECH=$1 MECH_CHECK=$5
O=$2
nohup /c/Users/benpe/ClashBot/research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L74/mechanic_fork/mech_fork.py --out $O --seeds $3 --opps gen \
  --arms plain --gen icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt --opp-gen icebow/data/pipeline/gen_v1_s0/gen_s0.pt \
  --forms-mode deck --device cpu --workers $4 --tail-cap 7200 --tau-plain 0.35 --census scratchpad/gauntlet/L70/pool_forms/loadable_decks.json \
  --hero-abilities --ability-policy v2 --opp-policy sample --opp-T 0.3 --xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 \
  --spell-aim rocket_area --own-effects --gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --log-aim log_barrel --lethal-rocket ot_behind \
  --xbow-dead-lane block --gate-hazard-threatened 2 --rocket-dead-target block --tau-threatened 0.2 --lethal-log on --behaviour-telemetry \
  > $O.log 2> $O.err &
echo $!
