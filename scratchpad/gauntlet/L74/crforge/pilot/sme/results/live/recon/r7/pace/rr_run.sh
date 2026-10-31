#!/usr/bin/env bash
# rr_run.sh OUTDIR NCHUNKS [worker flags] -- RECON-7 pace probe (pod 33903, CPUs 226-237): the D3 block's env (run_closed.sh), refusal reasons per match
OUT=$1; N=$2; shift 2
CB=/workspace/opp/cb; LIB=/workspace/crforge_main/5e8089a4/plain; TABLES=/workspace/oplm/tables/16.635.3; FAC=/workspace/smeR6/rr_fac
mkdir -p $FAC && cp $CB/scratchpad/gauntlet/L74/crforge/facade/CfCore.java $FAC/ && javac -nowarn -cp "$LIB/lib/*" -d $FAC $FAC/CfCore.java
unset ROYALE_HEROIW_PRESS
export HABITS_REC=1 PYTHONPATH=/workspace/smeR6/ov:$CB:/workspace/cfspeed/pylib ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  ROYALE_ENGINE=crforge ROYALE_RUNTIME=fin16-linux CRFORGE_LIB=$LIB/lib CRFORGE_TABLES=$TABLES CRFORGE_FACADE_BUILD=$FAC CRFORGE_XMX=1g \
  JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1"
cd $CB && W=${W:-4} taskset -c ${CPUS:-226-237} /workspace/venvf16/bin/python /workspace/smeR6/rr_probe.py $OUT $N "$@"
