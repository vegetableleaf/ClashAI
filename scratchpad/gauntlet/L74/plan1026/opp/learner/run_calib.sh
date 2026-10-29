#!/bin/bash
# OPP-LEARN-C calibration run on 33308 (lead 10-29: GPU1 only, RAM <= 30 GB, <= 40 actors, ONE lambda run at a time).
# usage: run_calib.sh RUN LAMBDA INIT CPUS [rl_royale k=v ...]   (tree /workspace/oplc/cb; log /workspace/oplc/logs/RUN.log)
# Restart after a stop: the same command + --resume (rl_royale resumes RUN from its latest checkpoint). Barrel decoy SIM off = as
# level B rows (run_closed.sh) and the smokes.
RUN=$1; LAM=$2; INIT=$3; CPUS=$4; shift 4
T=/workspace/oplc/cb; L=/workspace/crforge_main/fe364ceb/plain; TAB=/workspace/crforge_cache/tables/16.635.3; FAC=/workspace/oplc/fac
mkdir -p /workspace/oplc/logs
if [ ! -f "$FAC/CfCore.class" ]; then mkdir -p "$FAC" && cp "$T/scratchpad/gauntlet/L74/crforge/facade/CfCore.java" "$FAC/" \
  && javac -nowarn -cp "$L/lib/*" -d "$FAC" "$FAC/CfCore.java"; fi
cd $T || exit 1
export PYTHONPATH=$T ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 ROYALE_ENGINE=crforge CRFORGE_LIB=$L/lib CRFORGE_TABLES=$TAB \
  CRFORGE_FACADE_BUILD=$FAC CRFORGE_XMX=1g CUDA_VISIBLE_DEVICES=1 CUBLAS_WORKSPACE_CONFIG=:4096:8 \
  JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1"
exec taskset -c $CPUS /workspace/venvf16/bin/python -u -m pipeline.rl_royale --run $RUN \
  --config scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_calib.yaml init=$INIT beta0=$LAM beta_min=$LAM beta_max=$LAM \
  learner_device=cuda actor_device=cpu "$@" > /workspace/oplc/logs/$RUN.log 2>&1
