#!/bin/bash
# cputest.sh ENGINE TAG CPUS N [JAVA_TOOL_OPTIONS] -- pod 33308 (D2-G): one gate D3 worker (CLXIII vs E4, the first N seeds of
# the 741200 plan's job 0) without a profiler; bash `time` gives the process's wall / user / sys (all threads: Python + JVM).
# -> /workspace/d2/cpu/TAG.log. Env = gate.sh's.
E=$1; TAG=$2; CPUS=$3; N=$4; JO=${5:-}; CB=/workspace/d2/cb; PYX=/workspace/venvf16/bin/python; O=/workspace/d2/cpu
cd $CB || exit 1
unset ROYALE_HEROIW_PRESS
export HABITS_REC=1 PYTHONPATH=$CB ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 O3_PLAYS=1 ROYALE_ENGINE=$E ROYALE_RUNTIME=fin16-linux CRFORGE_LIB=/workspace/d2/stage/lib \
  CRFORGE_TABLES=/workspace/crforge_cache/tables/16.402.22 CRFORGE_FACADE_BUILD=/workspace/d2/build
[ -n "$JO" ] && export JAVA_TOOL_OPTIONS="$JO"
mkdir -p $O; rm -rf $O/$TAG.out
EX="--habit-log --live-levels --card-levels Rocket=16 Log=15 --ability-stats --ability-head-decode=sample --crown-log"
IN=/workspace/d2/ev/clxiii_rs_e4/clxiii_rs_e4_741200/inputs
ARGS=$("$PYX" scratchpad/gauntlet/L74/plan1026/d2g/prof_cmd.py $IN $O/$TAG.out $N "$EX")
{ time taskset -c $CPUS "$PYX" $ARGS ; } > $O/$TAG.log 2>&1
grep -c '"outcome"' $O/$TAG.out/matches.jsonl >> $O/$TAG.log
echo done >> $O/$TAG.log
