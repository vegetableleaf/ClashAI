#!/bin/bash
# run.sh TREE RUN CPUS NACT [rl_royale k=v ...] -- LOOP-OPP decision identity on the actor path (pod 32657): compile the
# tree's facade CfCore.java (+ the obsid builders, for D2-T2's obs check chained in when OBSCHECK=1), then the production
# config on crforge with oppcheck/sitecustomize.py: every opponent decision is re-made by pipeline.loop_opp and compared
# -> /workspace/loopopp/$RUN/<pid>.json (summ.py merges). Config = succ48_x_s101 + the k=v overrides (LOOPOPP_OVR copies).
T=$1; RUN=$2; CPUS=$3; N=$4; shift 4
W=/workspace/loopopp; B=$W/build_$RUN; L=${CF_LIB:-$W/lib_cfclone}; SRC=$T/scratchpad/gauntlet/L74/speed/crforge
CFG=scratchpad/gauntlet/L74/stepd/cfg/succ48_x_s101.yaml
mkdir -p $B $W/logs
javac -Xlint:all -d $B -cp "$L/*" $T/scratchpad/gauntlet/L74/crforge/facade/CfCore.java $SRC/CfSpeed.java $SRC/obsid/CfObsBind.java \
  $SRC/obsid/CfOppElixir.java $SRC/obsid/CfIdent.java $SRC/obsid/CfCue.java $SRC/obsid/CfPubObj.java > $B.javac.log 2>&1 || exit 1
cd $T || exit 1
OVR=$(/workspace/venvf16/bin/python -c 'import json,sys; print(json.dumps(sys.argv[1:]))' "$@")
HOOK=$T/scratchpad/gauntlet/L74/plan1026/pilot/opp/oppcheck
PP=$HOOK
[ "${OBSCHECK:-0}" = 1 ] && export D2T2_OBSCHECK=$W/${RUN}_obs OBSID_DIR=$SRC/obsid OBSID_RL=$T && PP=$HOOK:$T/scratchpad/gauntlet/L74/plan1026/d2g/d2t2/hook
export PYTHONPATH=$PP:$T:$W/pylib LOOPOPP_CHECK=$W/$RUN LOOPOPP_CFG=$CFG LOOPOPP_OVR="$OVR" \
  ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 RL_BATCH_SHA=1 ROYALE_ENGINE=crforge CRFORGE_LIB=$L \
  CRFORGE_TABLES=/workspace/crforge_cache/tables/16.402.22 CRFORGE_FACADE_BUILD=$B
exec taskset -c $CPUS timeout 14400 /workspace/venvf16/bin/python -u -m pipeline.rl_royale --run $RUN \
  --config $CFG n_actors=$N "$@" > $W/logs/$RUN.log 2>&1
