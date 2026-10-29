#!/bin/bash
# OPP-SIEGE2 probe lanes on 30408 (pod copy /workspace/siege/opp/cb2 = cb + patch_pod.py). Level B: CLXIII vs opponent,
# crforge 5e8089a4, G2 on, OPP T 1 (E4: 0.1), seeds as P2-OPP2. SIEGE_TGT=1 (board targets) costs ~5x wall per match
# (259 s vs 49 s median), so the target arms run ONE seed block (480 games) and the cell-T arms run without it.
# bash lanes.sh 1  -> tgtR = ftR + targets, seed 741200 (recorder control: outcome-identical to ftR5e), then tgtE4 (E4 + targets)
# bash lanes.sh 2  -> ct25 / ct50 = ftR with the CELL drawn at T .25 / .5 (card T 1), 4 seed blocks, no recorder
L=$1; R=/workspace/siege/score/rows; FT=/workspace/siege/opp/live/ft_s0/opp_ft_s0_R_sim.pt
run() { (cd /workspace/siege/score && env "$@" PY=/workspace/siege/venv/bin/python CB=/workspace/siege/opp/cb2 \
  LIB=/workspace/crforge_main/5e8089a4/plain CRFORGE_TABLES=/workspace/siege/crforge_cache/tables/16.402.22 G2_ON=on \
  bash /workspace/siege/opp/cb2/scratchpad/gauntlet/L74/opp_model/humanlike/run_closed.sh $NAME $R/$NAME $SEEDS); }
if [ "$L" = 1 ]; then
  SEEDS=741200; NAME=tgtR run SIEGE_TGT=1 OPP_CKPT=$FT OPP_T=1.0 CPUS=0-127 WORKERS=80
  SEEDS=741200; NAME=tgtE4 run SIEGE_TGT=1 CPUS=0-127 WORKERS=80
else
  SEEDS="741200 742000 742800 743600"
  NAME=ct25 run OPP_CKPT=$FT OPP_T=1.0 SIEGE_CELL_T=0.25 CPUS=128-255 WORKERS=60
  NAME=ct50 run OPP_CKPT=$FT OPP_T=1.0 SIEGE_CELL_T=0.5 CPUS=128-255 WORKERS=60
fi
echo "LANE $L DONE"
