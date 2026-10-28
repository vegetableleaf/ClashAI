#!/usr/bin/env bash
# V1-STRENGTH: pod environment for closed-loop CLXIII-vs-opponent games on 33553 (source this; run_closed.sh's env + the pilot's
# barrel-decoy SIM switch).  Overridable: CB LIB TABLES PY FACROOT.  Code tree = git archive of CODE_HEAD (see STRENGTH.md).
export CB=${CB:-/workspace/strength/cb}
export LIB=$(readlink -f "${LIB:-/workspace/crforge_main/fe364ceb/plain}")
export PY=${PY:-/workspace/venv/bin/python}
export TABLES=${CRFORGE_TABLES:-/workspace/crforge_cache/tables/16.635.3}
FACROOT=${FACROOT:-/workspace/strength/facade_$(basename "$(dirname "$LIB")")}
export FAC=$FACROOT
if [ ! -f "$FAC/CfCore.class" ]; then
  mkdir -p "$FAC" && cp "$CB/scratchpad/gauntlet/L74/crforge/facade/CfCore.java" "$FAC/" && javac -nowarn -cp "$LIB/lib/*" -d "$FAC" "$FAC/CfCore.java"
fi
unset ROYALE_HEROIW_PRESS
export HABITS_REC=1 PYTHONPATH=$CB ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 ROYALE_ENGINE=crforge ROYALE_RUNTIME=fin16-linux CRFORGE_LIB=$LIB/lib \
  CRFORGE_TABLES=$TABLES CRFORGE_FACADE_BUILD=$FAC CRFORGE_XMX=${CRFORGE_XMX:-1g} CRFORGE_BARREL_DECOY_SIM=1 \
  JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1"
