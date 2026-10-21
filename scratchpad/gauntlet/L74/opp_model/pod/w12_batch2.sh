#!/bin/bash
# W12 batch 2 (pod-local): wait for RUN's chain ALL_DONE, eval its u130 grafted, then eval the copied ckpt EXTRA.
#   bash /workspace/o3w12/w12_batch2.sh RUN EXTRA     (EXTRA ckpt at /workspace/o3w12/ckpt/rlarm_EXTRA_u0130_grafted.pt)
RUN=$1; EX=$2; export O3B=/workspace/o3w12
OPP=/workspace/cb_stepd/icebow/data/pipeline/o2/w7opp.pt
until grep -q ALL_DONE /workspace/stepd/rl_$RUN/chain.log 2>/dev/null; do sleep 60; done
for pair in "$RUN /workspace/cb_stepd/icebow/data/bench/rl_royale/rlarm_$RUN/rlarm_${RUN}_u0130_grafted.pt" "$EX $O3B/ckpt/rlarm_${EX}_u0130_grafted.pt"; do
  set -- $pair
  flock /workspace/stepd/claim.lock bash $O3B/opp_eval_fin15.sh w12_$1 $2 $OPP 0.1 40 - 741200 742000 743000 744000
done
