#!/bin/bash
# W12 driver (pod-local): wait for chain RUN ALL_DONE, then run opp_eval_fin15.sh on its grafted u130 vs w7opp (T0.1, decide 40).
#   setsid nohup bash /workspace/o3w12/w12_run.sh RUN [CKPT_RUN_DIR] > /dev/null 2>&1 < /dev/null &
RUN=$1; CD=${2:-$1}
export O3B=/workspace/o3w12
until grep -q ALL_DONE /workspace/stepd/rl_$RUN/chain.log 2>/dev/null; do sleep 60; done
CK=/workspace/cb_stepd/icebow/data/bench/rl_royale/rlarm_$CD/rlarm_${CD}_u0130_grafted.pt
OPP=/workspace/cb_stepd/icebow/data/pipeline/o2/w7opp.pt
echo "$(date -u +%FT%TZ) $RUN go $CK" >> $O3B/w12_$RUN.log
flock /workspace/stepd/claim.lock bash $O3B/opp_eval_fin15.sh w12_$RUN $CK $OPP 0.1 40 - 741200 742000 743000 744000
