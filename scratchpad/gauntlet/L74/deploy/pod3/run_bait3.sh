#!/bin/bash
# Pod 3 BAIT_CMP: Log Bait specialist vs generalist, both on the Log Bait BASE deck; opponent = CAL set c yardstick
# (rdef_e4 graft, T 0.1, census decks).  480 paired games each = seeds 0:240 evo + 0:240 lad.  Runs after ADAPT under the same locks.
set -u
ROOT=/workspace/wk_adapt; W=$ROOT/scratchpad/gauntlet/L74/weekend
D=/workspace/results/wk/BAIT_CMP; EV=$D/evals; mkdir -p $EV; rm -f $D/DONE
PY=/workspace/venv/bin/python; export ROYALE_RUNTIME=20261006-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 CB_MAIN=$ROOT
CKR=icebow/data/bench/rl_royale; WORKERS=${BAIT_WORKERS:-12}
SPEC=$CKR/wk_bait/wk_bait_u0060_g.pt
GEN=$CKR/rseries_r3c/rseries_r3c_u0030_barrel2k_cellref_towerref_w2.pt
YARD=$CKR/rdef_e4/rdef_e4_u0020_barrel2k_cellref_towerref_w2.pt
trap '[ -s $D/SUMMARY.txt ] || echo "BAIT_CMP: no summary written; see $D/stage.log" > $D/SUMMARY.txt; touch $D/DONE' EXIT
cd $ROOT
for name in gen spec; do
  ck=$GEN; [ $name = spec ] && ck=$SPEC
  for c in evo lad; do
    [ -s $EV/${name}_$c/summary.json ] && continue
    rm -rf $EV/${name}_$c
    case $c in evo) DK=scratchpad/gauntlet/L70/pool_forms/loadable_decks.json; S0=0 ;; lad) DK=scratchpad/gauntlet/L73/rl_r2/loadable_decks_ladder.json; S0=0 ;; esac
    echo "[$(date -u +%T)] eval $name $c" >> $D/stage.log
    $PY $W/bait_base_s0.py --out $EV/${name}_$c --seeds $S0:$((S0+240)) --opps gen --arms plain --gen $ck --opp-gen $YARD \
      --forms-mode deck --device cpu --workers $WORKERS --tail-cap 7200 --tau-plain 0.35 --census $DK --hero-abilities --ability-policy v2 \
      --opp-policy sample --opp-T 0.1 --own-effects > $EV/${name}_$c.log 2>&1 || { echo "FAILED $name $c" >> $D/stage.log; exit 1; }
  done
done
cd $W && $PY $W/bait_cmp_summary.py $EV $D/SUMMARY.txt > $D/summary.out 2>&1
echo "[$(date -u +%T)] BAIT_CMP done" >> $D/stage.log
