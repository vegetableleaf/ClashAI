#!/bin/bash
# long_train.sh RUN -- 10-22 (lead): training-only launcher for the long run (stepd_chain.sh's train step and env, without
# its u0130 / eval steps). Resumes from <run>_latest.pt when present. Log: /workspace/stepd/rl_<RUN>/train.log.
RUN=$1; CB=/workspace/cb_stepd; O=/workspace/stepd/rl_$RUN; R=rlarm_$RUN; RL=icebow/data/bench/rl_royale
mkdir -p $O; cd $CB || exit 1
sed -i 's/\r$//' scratchpad/gauntlet/L74/stepd/cfg/$RUN.yaml
unset ROYALE_HEROIW_PRESS
export PYTHONPATH=$CB ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
ulimit -n 65536
RES=; [ -f $RL/$R/${R}_latest.pt ] && RES=--resume
echo "$(date -u +%FT%TZ) long train $R $RES" >> $O/chain.log
ROYALE_RUNTIME=fin15-linux setsid nohup flock /workspace/cpu.lock /workspace/venvf15/bin/python -m pipeline.rl_royale \
  --config scratchpad/gauntlet/L74/stepd/cfg/$RUN.yaml --run $R $RES >> $O/train.log 2>&1 < /dev/null &
sleep 30; pgrep -f "rl_royale.*$R" | head -3; tail -2 $O/train.log
