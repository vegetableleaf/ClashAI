#!/bin/bash
# smoke.sh ENGINE(crforge|royalesim) RUN: rl_royale --smoke on succ48_x_s101 (D2-T's command), batch shas logged
source /workspace/lrn/cb/scratchpad/gauntlet/L74/plan1026/pilot/lrn/env.sh
export ROYALE_ENGINE=$1 RL_BATCH_SHA=1
cd $CB && mkdir -p /workspace/lrn/logs
exec timeout 7200 $PY -u -m pipeline.rl_royale --run $2 --config scratchpad/gauntlet/L74/stepd/cfg/succ48_x_s101.yaml --smoke \
  actor_device=cpu learner_device=cpu > /workspace/lrn/logs/$2.log 2>&1
