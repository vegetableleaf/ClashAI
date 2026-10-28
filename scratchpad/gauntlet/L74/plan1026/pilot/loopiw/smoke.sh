#!/bin/bash
# smoke.sh ENGINE RUN LIB -- LOOP-IW: rl_royale --smoke of the production config (pod 32657, tree /workspace/loopiw/cb)
E=$1; RUN=$2; L=$3; T=/workspace/loopiw/cb; B=/workspace/loopiw/build_facade_$(basename $L)
mkdir -p $B /workspace/loopiw/logs
javac -d $B -cp "$L/*" $T/scratchpad/gauntlet/L74/crforge/facade/CfCore.java > $B.javac.log 2>&1 || exit 1
cd $T || exit 1
export PYTHONPATH=$T:/workspace/loopiw/pylib ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 RL_BATCH_SHA=1 ROYALE_ENGINE=$E \
  CRFORGE_LIB=$L CRFORGE_TABLES=/workspace/crforge_cache/tables/16.402.22 CRFORGE_FACADE_BUILD=$B
exec timeout 7200 /workspace/venvf16/bin/python -u -m pipeline.rl_royale --run $RUN \
  --config scratchpad/gauntlet/L74/stepd/cfg/succ48_x_s101.yaml --smoke actor_device=cpu learner_device=cpu \
  > /workspace/loopiw/logs/$RUN.log 2>&1
