#!/bin/bash
# devcost.sh DEV N CPUS -- PILOT-LOOP: process CPU per match of one gate D3 worker (crforge, CLXIII vs E4, first N seeds of
# the 741200 plan's job 0; = d2g/prof.sh's command without cProfile) with the policy forward on DEV (cpu | cuda).
DEV=$1; N=$2; CPUS=$3; T=$DEV$N; CB=/workspace/d2/cb; PYX=/workspace/venvf16/bin/python; O=/workspace/pilot_loop/devcost
cd $CB || exit 1
unset ROYALE_HEROIW_PRESS
export HABITS_REC=1 PYTHONPATH=$CB OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  ROYALE_HEROIW_FORM=hero O3_PLAYS=1 ROYALE_ENGINE=crforge ROYALE_RUNTIME=fin16-linux CRFORGE_LIB=/workspace/d2/stage/lib \
  CRFORGE_TABLES=/workspace/crforge_cache/tables/16.402.22 CRFORGE_FACADE_BUILD=/workspace/d2/build CUDA_VISIBLE_DEVICES=1
mkdir -p $O; rm -rf $O/$T.out
EX="--habit-log --live-levels --card-levels Rocket=16 Log=15 --ability-stats --ability-head-decode=sample --crown-log"
IN=/workspace/d2/ev/clxiii_rs_e4/clxiii_rs_e4_741200/inputs
ARGS=$($PYX scratchpad/gauntlet/L74/plan1026/d2g/prof_cmd.py $IN $O/$T.out $N "$EX")
ARGS=${ARGS/--device cpu/--device $DEV}
echo "$ARGS" > $O/$T.cmd
TIMEFORMAT="user %U sys %S wall %R"; { time taskset -c $CPUS $PYX $ARGS > $O/$T.log 2>&1 ; } 2> $O/$T.time
echo "rows $(grep -c '"outcome"' $O/$T.out/matches.jsonl 2>/dev/null)" >> $O/$T.time
