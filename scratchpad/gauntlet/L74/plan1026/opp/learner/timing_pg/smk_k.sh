#!/bin/bash
# OPP-LEARN-D final-code smokes, ONE AT A TIME (lead): timing_pg 32 production then fast loop; absent-key identity
# s48 new (vs oplcd_s48_base) and the timing-head learner off (bot + th_anchor 1.0) base vs new.
set -f
O=/workspace/oplc; LG=$O/logsd; L=/workspace/crforge_main/fe364ceb/plain; TAB=/workspace/crforge_cache/tables/16.635.3
BOT=scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_bot_smoke.yaml; S48=scratchpad/gauntlet/L74/stepd/cfg/succ48_x_s101.yaml
K="th_anchor=10.0 timing_pg=32 freeze_heads=[ability]"
prod() {
  T=$1; RUN=$2; CFG=$3; shift 3
  (cd $T && env PYTHONPATH=$T ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 RL_BATCH_SHA=1 ROYALE_ENGINE=crforge CRFORGE_LIB=$L/lib \
    CRFORGE_TABLES=$TAB CRFORGE_FACADE_BUILD=$O/fac_$(basename $T) CRFORGE_XMX=1g JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1" \
    taskset -c 158-161 timeout 7200 /workspace/venvf16/bin/python -u -m pipeline.rl_royale --run $RUN --config $CFG --smoke \
    actor_device=cpu learner_device=cpu "$@" > $LG/$RUN.log 2>&1; echo "$RUN rc $?" >> $LG/smk_k.rc)
}
prod $O/cbd oplcd_k32_prod $BOT $K
CB=$O/cbd TABLES=$TAB LOGS=$LG XMX=1g bash $O/fl_pod.sh fast oplcd_k32_fl 162-169 $BOT $K --smoke; echo "oplcd_k32_fl rc $?" >> $LG/smk_k.rc
prod $O/cbd oplcd_s48_new2 $S48
prod $O/cbd_base oplcd_bot_base $BOT th_anchor=1.0
prod $O/cbd oplcd_bot_new $BOT th_anchor=1.0
echo SMK_DONE >> $LG/smk_k.rc
