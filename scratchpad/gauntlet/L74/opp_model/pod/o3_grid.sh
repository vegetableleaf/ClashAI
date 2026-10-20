#!/bin/bash
# O3 tempo grid (one pod's share): sequential opp_eval.sh runs, 480 games each (seed 741200), CLX learner, all16.
#   setsid nohup bash /workspace/o3/o3_grid.sh OPP_CKPT "T:DE:RT T:DE:RT ..." > /dev/null 2>&1 < /dev/null &
# NAME = o3_<opp tag>_T<T>_d<DE>_r<RT>. The CPU lock inside opp_eval.sh serialises with any other eval on the pod.
OPP=$1; CONFIGS=$2; TAG=${TAG:-$(basename ${OPP%.pt})}
CLX=icebow/data/bench/rl_royale/rlarm_stepd_ctrl_nos2/rlarm_stepd_ctrl_nos2_u0130_grafted.pt
for c in $CONFIGS; do
  IFS=: read -r T DE RT <<< "$c"
  bash /workspace/o3/opp_eval.sh o3_${TAG}_T${T}_d${DE}_r${RT} $CLX $OPP $T $DE $RT 741200
done
touch /workspace/o3/GRID_DONE_$TAG
