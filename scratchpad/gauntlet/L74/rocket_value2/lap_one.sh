#!/bin/bash
# Laptop (Windows) version of vm_one.sh: one (arm, census) job on a seed list, WORKERS processes at below-normal priority (the wrappers lower it),
# CPU only.  bash lap_one.sh ARM CENSUS SEEDS OUTDIR [WORKERS=3]    (CENSUS evo | lad | air)   ARM flags from arms_all.txt (+ plc9)
name=$1; s=$2; seeds=$3; O=$4; W=${5:-3}
R=/c/Users/benpe/ClashBot/.claude/worktrees/agent-a67f26ceb5d77048a
cd $R
export ROYALE_RUNTIME=20261006 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CUDA_VISIBLE_DEVICES= PYTHONIOENCODING=utf-8
PY=/c/Users/benpe/ClashBot/research/ext/Royale/.venv/Scripts/python.exe
D=/c/Users/benpe/ClashBot
CK=$D/icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt
GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
case $s in evo) c=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json;; lad) c=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json;; air) c=scratchpad/gauntlet/L74/rocket_value2/air_census.json;; esac
c=$D/${c#}
[ $s = air ] && c=$R/scratchpad/gauntlet/L74/rocket_value2/air_census.json
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area --own-effects
    --gate-decode hazard_below_tau --gate-hazard-min-elixir 9 --gate-hazard-threatened 2 --log-aim log_barrel
    --lethal-rocket ot_behind --xbow-dead-lane block --rocket-dead-target block --tau-threatened 0.2 --lethal-log on --behaviour-telemetry)
flags=$(awk -v n=$name '$1==n{$1=""; print}' $R/scratchpad/gauntlet/L74/rocket_value2/arms_run.txt | tr -d '\r')
mkdir -p $O; export FIRE_DIR=$O/fires_${name}_$s; mkdir -p $FIRE_DIR
case $name in plc*) export PLACEBO=1;; *) unset PLACEBO;; esac
WRAP=${WRAP:-scratchpad/gauntlet/L74/rocket_value2/rv2_diag_s0.py}
$PY $WRAP --out $O/${name}_$s --seeds $seeds --opps gen --arms plain --gen $CK \
  --opp-gen $GEN1 --forms-mode deck --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census $c --hero-abilities \
  --ability-policy v2 --opp-policy sample --opp-T 0.3 "${LV[@]}" $flags > $O/${name}_$s.log 2>&1
echo "$name $s rc=$? $(date +%T)" >> $O/sim.log
