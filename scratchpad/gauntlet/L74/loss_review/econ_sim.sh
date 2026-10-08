#!/bin/bash
# L74 econ-gap SIM arms (isolated ~/loss_review/repo, patched by econ_sim_patch.py; never ~/ClashBot). CPU only, nice.
# v3 benchmark as W4 (vs gen v1 sampling T .3), seeds 0:240 x census (evo) + ladder (lad) = 480 matches per arm, paired.
#   stack      = rseries_r3c_u0030_barrel2k_cellref + live options (as live stack2k_cellref family / W4 v3 base)
#   stack_bias = stack + LR_OPP_BIAS=0.34 (the live opponent counter's measured over-read)
#   r1e        = rseries_r1e31_u0155, flat tau .35, argmax decoding (as the live R1e family)
cd ~/loss_review/repo
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=~/venv/bin/python; O=~/loss_review/sim; W=${WORKERS:-12}; LOG=$O/sim.log
STACK=icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref.pt
R1E=icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt
GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
EVO=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json; LAD=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area)
run() { local name=$1 ck=$2; shift 2
  for s in evo lad; do d=$EVO; [ $s = lad ] && d=$LAD
    nice $PY -m pipeline.search_s0 --out $O/${name}_$s --seeds 0:240 --opps gen --arms plain --gen $ck --opp-gen $GEN1 \
      --forms-mode deck --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census $d --hero-abilities \
      --ability-policy v2 --behaviour-telemetry --opp-policy sample --opp-T 0.3 "$@" > $O/${name}_$s.log 2>&1
    echo "$name $s rc=$? $(date +%T)" >> $LOG; done; }
run stack $STACK "${LV[@]}"
LR_OPP_BIAS=0.34 run stack_bias $STACK "${LV[@]}"
run r1e $R1E
echo DONE >> $LOG
