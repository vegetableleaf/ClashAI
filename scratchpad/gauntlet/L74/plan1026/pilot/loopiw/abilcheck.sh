#!/bin/bash
# abilcheck.sh RUN NACT [rl_royale k=v ...] -- LOOP-IW identity run (pod 32657): compile CfCore + the obsid builders +
# CfAbil against the CF-CLONE lib into /workspace/loopiw/build_$RUN, then the production config on crforge with
# hook/sitecustomize.py (LIW_OUT): every actor compares CfAbil with production -> /workspace/loopiw/$RUN/<pid>.json.
# Resume = run again with a new RUN (each run is self-contained). Summary: python abil_sum.py /workspace/loopiw/$RUN
RUN=$1; N=$2; shift 2
T=/workspace/loopiw/cb; L=${CF_LIB:-/workspace/loopiw/lib}; B=/workspace/loopiw/build_$RUN; S=$T/scratchpad/gauntlet/L74/speed/crforge
H=$T/scratchpad/gauntlet/L74/plan1026/pilot/loopiw/hook
mkdir -p $B /workspace/loopiw/logs
javac -d $B -cp "$L/*" $T/scratchpad/gauntlet/L74/crforge/facade/CfCore.java $S/CfSpeed.java $S/obsid/CfObsBind.java \
  $S/obsid/CfOppElixir.java $S/obsid/CfIdent.java $S/obsid/CfCue.java $S/obsid/CfPubObj.java $S/obsid/CfAbil.java \
  > $B.javac.log 2>&1 || exit 1
cd $T || exit 1
export PYTHONPATH=$H:$T:/workspace/loopiw/pylib LIW_OUT=/workspace/loopiw/$RUN OBSID_DIR=$S/obsid OBSID_RL=$T \
  JAVA_TOOL_OPTIONS="--add-modules=jdk.incubator.foreign --enable-native-access=ALL-UNNAMED" \
  ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 RL_BATCH_SHA=1 ROYALE_ENGINE=crforge CRFORGE_LIB=$L \
  CRFORGE_TABLES=/workspace/crforge_cache/tables/16.402.22 CRFORGE_FACADE_BUILD=$B
exec timeout 14400 /workspace/venvf16/bin/python -u -m pipeline.rl_royale --run $RUN \
  --config scratchpad/gauntlet/L74/stepd/cfg/succ48_x_s101.yaml n_actors=$N "$@" > /workspace/loopiw/logs/$RUN.log 2>&1
