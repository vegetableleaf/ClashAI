#!/bin/bash
# prof.sh ENGINE CPUS N -- pod 33308 (D2-G): cProfile one gate D3 worker (CLXIII vs E4, the first N seeds of the 741200 plan's
# job 0) on ENGINE; writes /workspace/d2/prof/ENGINE.{prof,log,txt}. Env = gate.sh's.
E=$1; CPUS=$2; N=${3:-3}; CB=/workspace/d2/cb; PYX=/workspace/venvf16/bin/python; O=/workspace/d2/prof
cd $CB || exit 1
unset ROYALE_HEROIW_PRESS
export HABITS_REC=1 PYTHONPATH=$CB ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 O3_PLAYS=1 ROYALE_ENGINE=$E ROYALE_RUNTIME=fin16-linux CRFORGE_LIB=/workspace/d2/stage/lib \
  CRFORGE_TABLES=/workspace/crforge_cache/tables/16.402.22 CRFORGE_FACADE_BUILD=/workspace/d2/build
mkdir -p $O; rm -rf $O/$E.out
EX="--habit-log --live-levels --card-levels Rocket=16 Log=15 --ability-stats --ability-head-decode=sample --crown-log"
IN=/workspace/d2/ev/clxiii_rs_e4/clxiii_rs_e4_741200/inputs
ARGS=$("$PYX" scratchpad/gauntlet/L74/plan1026/d2g/prof_cmd.py $IN $O/$E.out $N "$EX")
taskset -c $CPUS "$PYX" -m cProfile -o $O/$E.prof $ARGS > $O/$E.log 2>&1
"$PYX" -c "import pstats,sys; pstats.Stats(sys.argv[1]).sort_stats('cumulative').print_stats(45)" $O/$E.prof > $O/$E.txt
"$PYX" -c "import pstats,sys; pstats.Stats(sys.argv[1]).sort_stats('tottime').print_stats(30)" $O/$E.prof >> $O/$E.txt
echo done >> $O/$E.log
