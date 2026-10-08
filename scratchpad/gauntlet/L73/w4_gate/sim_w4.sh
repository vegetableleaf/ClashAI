#!/bin/bash
# W4 SIM (isolated copy ~/w4/repo; never ~/ClashBot): live config base vs hazard gate decoding.
# v2 = vs S1 (never initiates) seeds 0:96; v3 = vs gen v1 sampling T .3, seeds 0:480; both x census (EVO) + ladder (LAD).
cd ~/w4/repo
export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
PY=~/venv/bin/python; O=~/w4/sim; W=${WORKERS:-16}; LOG=$O/sim.log
CK=icebow/data/bench/rl_royale/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref.pt; GEN1=icebow/data/pipeline/gen_v1_s0/gen_s0.pt
EVO=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json; LAD=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json
LV=(--xbow-class class_sample --xbow-class-floor 0.3 --tau-phase 0.35 0.45 0.55 --spell-aim rocket_area)
run() { local name=$1 opp=$2 seeds=$3; shift 3
  for s in evo lad; do d=$EVO; [ $s = lad ] && d=$LAD
    nice $PY -m pipeline.search_s0 --out $O/${name}_$s --seeds $seeds --opps $opp --arms plain --gen $CK --opp-gen $GEN1 \
      --forms-mode deck --device cpu --workers $W --tail-cap 7200 --tau-plain 0.35 --census $d --hero-abilities \
      --ability-policy v2 --behaviour-telemetry --opp-policy sample --opp-T 0.3 "${LV[@]}" "$@" > $O/${name}_$s.log 2>&1
    echo "$name $s rc=$? $(date +%T)" >> $LOG; done; }
for arm in base hbt haz; do
  X=(); [ $arm = hbt ] && X=(--gate-decode hazard_below_tau); [ $arm = haz ] && X=(--gate-decode hazard)
  run v2_$arm s1 0:96 "${X[@]}"
  run v3_$arm gen 0:480 "${X[@]}"
done
echo DONE >> $LOG
