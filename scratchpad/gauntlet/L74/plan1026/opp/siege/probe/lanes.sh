#!/bin/bash
# OPP-SIEGE2 probe queue on 30408 (pod copy /workspace/siege/opp/cb2 = cb + patch_pod.py). Level B: CLXIII vs opponent,
# crforge 5e8089a4, G2 on, OPP T 1 (E4: 0.1). 30408 cgroup = 54.4 CPUs and 62 GB RAM (~1 GB per worker): ONE queue, 44
# workers were used (two lanes of 80 + 60 hit the memory limit at 11:19 UTC and stalled the pod); from 13:55 UTC the lead
# runs an arm on 30408 (GPU + CPUs 200-221, 25-30 GB): default now 25 workers on CPUs 0-199.
# bash lanes.sh quick -> 480-game blocks (seed 741200): tgtR (ftR + SIEGE_TGT board targets; recorder control vs ftR5e),
#                        ct25 (ftR, cell T .25), tgtE4 (E4 + targets), ct50 (cell T .5)
# bash lanes.sh full NAME T -> the remaining 3 seed blocks of a cell-T arm (run_closed skips finished blocks)
R=/workspace/siege/score/rows; FT=/workspace/siege/opp/live/ft_s0/opp_ft_s0_R_sim.pt
run() { (cd /workspace/siege/score && env "$@" PY=/workspace/siege/venv/bin/python CB=/workspace/siege/opp/cb2 \
  LIB=/workspace/crforge_main/5e8089a4/plain CRFORGE_TABLES=/workspace/siege/crforge_cache/tables/16.402.22 G2_ON=on \
  CPUS=${CPUS:-0-199} WORKERS=${WORKERS:-25} bash /workspace/siege/opp/cb2/scratchpad/gauntlet/L74/opp_model/humanlike/run_closed.sh $NAME $R/$NAME $SEEDS); }
if [ "$1" = quick ]; then
  SEEDS=741200
  NAME=tgtR run SIEGE_TGT=1 OPP_CKPT=$FT OPP_T=1.0
  NAME=ct25 run OPP_CKPT=$FT OPP_T=1.0 SIEGE_CELL_T=0.25
  NAME=tgtE4 run SIEGE_TGT=1
  NAME=ct50 run OPP_CKPT=$FT OPP_T=1.0 SIEGE_CELL_T=0.5
else
  SEEDS="741200 742000 742800 743600"; NAME=$2 run OPP_CKPT=$FT OPP_T=1.0 SIEGE_CELL_T=$3
fi
echo "QUEUE $* DONE"
