#!/bin/bash
# obscheck.sh TREE SRC RUN CPUS NACT [rl_royale k=v ...] -- D2-T2 item 2a first check (pod 33308): compile the tree's
# CfCore.java + CfSpeed + the obsid builders (SRC = a copy of speed/crforge) into /workspace/d2t2/build_$RUN, then the
# production config on crforge with hook/sitecustomize.py (D2T2_OBSCHECK): every actor compares the builders with the
# production row per key -> /workspace/d2t2/$RUN/<pid>.json.
T=$1; SRC=$2; RUN=$3; CPUS=$4; N=$5; shift 5
B=/workspace/d2t2/build_$RUN; L=/workspace/d2/stage/lib
mkdir -p $B /workspace/d2t/logs
javac -Xlint:all -d $B -cp "$L/*" $T/scratchpad/gauntlet/L74/crforge/facade/CfCore.java $SRC/CfSpeed.java $SRC/obsid/CfObsBind.java \
  $SRC/obsid/CfOppElixir.java $SRC/obsid/CfIdent.java $SRC/obsid/CfCue.java $SRC/obsid/CfPubObj.java > $B.javac.log 2>&1 || exit 1
cd $T || exit 1
export PYTHONPATH=/workspace/d2t2/hook:$T:/workspace/d2/stage/pylib D2T2_OBSCHECK=/workspace/d2t2/$RUN OBSID_DIR=$SRC/obsid OBSID_RL=$T \
  ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 RL_BATCH_SHA=1 ROYALE_ENGINE=crforge CRFORGE_LIB=$L \
  CRFORGE_TABLES=/workspace/crforge_cache/tables/16.402.22 CRFORGE_FACADE_BUILD=$B
exec taskset -c $CPUS timeout 14400 /workspace/venvf16/bin/python -u -m pipeline.rl_royale --run $RUN \
  --config scratchpad/gauntlet/L74/stepd/cfg/succ48_x_s101.yaml n_actors=$N "$@" > /workspace/d2t/logs/$RUN.log 2>&1
