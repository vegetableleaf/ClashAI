#!/bin/bash
# OPP-LEARN-B pod smoke (33903, CPUs 200-203; lead 10-28). usage: pod_smoke.sh TREE RUN CONFIG
# A REAL rl_royale --smoke on crforge fe364ceb + tables 16.635.3, CPU learner + 1 CPU actor, RL_BATCH_SHA=1 (W16 shas logged).
# Trees: /workspace/opplearn/cb_base (git archive of the base commit) and /workspace/opplearn/cb (+ this change); icebow/data
# -> /workspace/icebow_data; opp_ckpt/ -> the v0 opponent. Log /workspace/opplearn/logs/RUN.log.
T=$1; RUN=$2; CFG=$3
L=/workspace/crforge_main/fe364ceb/plain; TAB=/workspace/opplearn/tables/16.635.3; FAC=/workspace/opplearn/fac_$(basename $T)
mkdir -p /workspace/opplearn/logs
if [ ! -f "$FAC/CfCore.class" ]; then mkdir -p "$FAC" && cp "$T/scratchpad/gauntlet/L74/crforge/facade/CfCore.java" "$FAC/" \
  && javac -nowarn -cp "$L/lib/*" -d "$FAC" "$FAC/CfCore.java"; fi
cd $T || exit 1
export PYTHONPATH=$T ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 RL_BATCH_SHA=1 ROYALE_ENGINE=crforge CRFORGE_LIB=$L/lib CRFORGE_TABLES=$TAB \
  CRFORGE_FACADE_BUILD=$FAC CRFORGE_XMX=1g JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1"
exec taskset -c 200-203 timeout 7200 /workspace/venvf16/bin/python -u -m pipeline.rl_royale --run $RUN --config $CFG --smoke \
  actor_device=cpu learner_device=cpu > /workspace/opplearn/logs/$RUN.log 2>&1
