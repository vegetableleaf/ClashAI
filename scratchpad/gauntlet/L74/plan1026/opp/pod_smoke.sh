#!/usr/bin/env bash
# P2-OPP smoke on 33308: env = run_closed.sh's + gap.run_arm's. usage: smoke.sh OPP_CKPT OUT [SEEDS] [OPP_T]
set -euo pipefail
CB=/workspace/opp/cbs; LIB=/workspace/crforge_main/a677e080/plain; TABLES=/workspace/crforge_cache/tables/16.402.22
FAC=/workspace/opp/score/facade
if [ ! -f "$FAC/CfCore.class" ]; then mkdir -p "$FAC" && cp "$CB/scratchpad/gauntlet/L74/crforge/facade/CfCore.java" "$FAC/" && javac -nowarn -cp "$LIB/lib/*" -d "$FAC" "$FAC/CfCore.java"; fi
cd $CB
export HABITS_REC=1 PYTHONPATH=$CB ROYALE_HEROIW_FORM=hero ROYALE_HEROIW_PRESS=live OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 ROYALE_ENGINE=crforge ROYALE_RUNTIME=fin16-linux CRFORGE_LIB=$LIB/lib \
  CRFORGE_TABLES=$TABLES CRFORGE_FACADE_BUILD=$FAC CRFORGE_XMX=1g JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1"
exec /workspace/venvf16/bin/python scratchpad/gauntlet/L74/plan1026/opp/smoke_closed.py --opp "$1" --out "$2" --seeds "${3:-741200,741201}" --opp-T "${4:-1.0}" --python /workspace/venvf16/bin/python
