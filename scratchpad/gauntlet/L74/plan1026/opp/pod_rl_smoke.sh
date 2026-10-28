#!/bin/bash
# pod_rl_smoke.sh TREE RUN -- P2-OPP: a real rl_royale --smoke (succ48_x_s101, crforge a677e080, batch shas logged) in the code
# copy TREE on 33308; two trees (before / after a pipeline change) must log the same batch shas. Log /workspace/opp/logs/RUN.log.
T=$1; RUN=$2; L=/workspace/crforge_main/a677e080/plain/lib; B=/workspace/opp/score/facade
mkdir -p /workspace/opp/logs
cd $T || exit 1
export PYTHONPATH=$T ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 RL_BATCH_SHA=1 ROYALE_ENGINE=crforge CRFORGE_LIB=$L CRFORGE_TABLES=/workspace/crforge_cache/tables/16.402.22 \
  CRFORGE_FACADE_BUILD=$B
exec timeout 7200 /workspace/venvf16/bin/python -u -m pipeline.rl_royale --run $RUN \
  --config scratchpad/gauntlet/L74/stepd/cfg/succ48_x_s101.yaml --smoke actor_device=cpu learner_device=cpu \
  > /workspace/opp/logs/$RUN.log 2>&1
