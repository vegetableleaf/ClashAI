#!/bin/bash
# Rocket + Tornado combo SIM on a Linux pod, in stages (every CPU-heavy stage under the shared lock).
#   REPO=/workspace/wt_rocket OUT=/workspace/results/rocket PY=/workspace/venv/bin/python P=28 bash pod_combo.sh A|B|C
#   A  BASE with every board logged, evo + ladder + air-heavy pool, 240 seeds each (720 games)      -> $OUT/a
#   (replay)  each variant's first trigger on those boards -> seed subsets -> jobs                  -> $OUT/seeds
#   B  the combo arms + their Rocket-alone twins + references on the seeds they can differ on       -> $OUT/b
#   C  summaries: paired wins + CI, combo fires, units in the blast at impact vs the lone Rocket
REPO=${REPO:-/workspace/wt_rocket}; OUT=${OUT:-/workspace/results/rocket}; PY=${PY:-/workspace/venv/bin/python}; P=${P:-28}
LOCK=${LOCK:-/workspace/cpu.lock}
ARMS=${ARMS:-cb7,cb7_ro,cb9,cb9_ro,cb7_th,cb7_th_ro,cbon7_th,de7_th,de9_e8}
export ROYALE_RUNTIME=${ROYALE_RUNTIME:-20261006-linux} OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
R=scratchpad/gauntlet/L74/rocket_value2
cd $REPO; mkdir -p $OUT
case $1 in
A)
  $PY $R/mk_jobs.py base $OUT/jobs_a.json
  flock $LOCK $PY $R/pod_driver.py --repo $REPO --out $OUT/a --jobs $OUT/jobs_a.json --p $P --py $PY ;;
replay)
  for c in evo lad air; do
    $PY $R/replay_triggers.py $OUT/a $c $R/variants.json --workers 8 | cut -c1-300
  done
  $PY $R/mk_subsets.py $OUT/a $OUT/seeds --censuses evo,lad,air --controls 8 ;;
B)
  $PY $R/mk_jobs.py arms $OUT/jobs_b.json --seeds-dir $OUT/seeds --arms $ARMS
  flock $LOCK $PY $R/pod_driver.py --repo $REPO --out $OUT/b --jobs $OUT/jobs_b.json --p $P --py $PY ;;
C)
  for set in evo,lad air; do
    echo "=== census $set"; $PY $R/sim_summary2.py $OUT/a $OUT/b $ARMS --censuses $set
  done
  for arm in cb7 cb9 cb7_th; do echo "=== $arm vs ${arm}_ro"; $PY $R/diag_combo.py $OUT/b $arm ${arm}_ro evo,lad,air; done ;;
esac
