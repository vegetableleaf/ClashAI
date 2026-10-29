#!/bin/bash
# OPP-LEARN-D pod smokes on 33308 (CPUs 150-185; the calibration arms use 100-121 / 124-145). usage: bash chain_d.sh [WAVE]
# Trees: /workspace/oplc/cbd_base (= cb2 = HEAD e9d2a71 content) and /workspace/oplc/cbd (+ timing_pg). Logs /workspace/oplc/logsd.
#   wave 1: s48 base / new (absent-key identity, gate model), tpg_prod (production rl_royale --smoke, timing_pg on),
#           tpg_fl (FAST LOOP smoke, same config, DUMP=1 -> fast_msg_u0000.pkl for the compare)
#   wave 2: bot base / new (absent-key identity, timing-head learner, th_anchor on), cmp (compare.py on tpg_fl's u0000 msg)
set -f                                                          # no globbing: freeze_heads=[ability] is literal
O=/workspace/oplc; LG=$O/logsd; mkdir -p $LG
L=/workspace/crforge_main/fe364ceb/plain; TAB=/workspace/crforge_cache/tables/16.635.3
CF=scratchpad/gauntlet/L74/plan1026/opp/learner
BOT=$CF/opp_learner_bot_smoke.yaml; S48=scratchpad/gauntlet/L74/stepd/cfg/succ48_x_s101.yaml
TPG="th_anchor=10.0 timing_pg=true freeze_heads=[ability]"
prod() {  # TREE RUN CPUS CONFIG [overrides]: a REAL rl_royale --smoke (production actors), CPU learner + 1 CPU actor
  T=$1; RUN=$2; C=$3; CFG=$4; shift 4
  FAC=$O/fac_$(basename $T)
  (cd $T && env PYTHONPATH=$T ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 RL_BATCH_SHA=1 ROYALE_ENGINE=crforge CRFORGE_LIB=$L/lib \
    CRFORGE_TABLES=$TAB CRFORGE_FACADE_BUILD=$FAC CRFORGE_XMX=1g JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1" \
    taskset -c $C timeout 7200 /workspace/venvf16/bin/python -u -m pipeline.rl_royale --run $RUN --config $CFG --smoke \
    actor_device=cpu learner_device=cpu "$@" > $LG/$RUN.log 2>&1; echo "$RUN rc $?" >> $LG/chain_d.rc)
}
for T in $O/cbd_base $O/cbd; do                                 # the CfCore facade per tree (pod_smoke.sh's rule)
  FAC=$O/fac_$(basename $T)
  [ -f "$FAC/CfCore.class" ] || { mkdir -p $FAC && cp $T/scratchpad/gauntlet/L74/crforge/facade/CfCore.java $FAC/ \
    && javac -nowarn -cp "$L/lib/*" -d $FAC $FAC/CfCore.java; }
done
if [ "${1:-1}" = 1 ]; then
  prod $O/cbd_base oplcd_s48_base 150-153 $S48 &
  prod $O/cbd oplcd_s48_new 154-157 $S48 &
  prod $O/cbd oplcd_tpg_prod 158-161 $BOT $TPG &
  (CB=$O/cbd TABLES=$TAB LOGS=$LG DUMP=1 XMX=1g bash $O/fl_pod.sh fast oplcd_tpg_fl 162-169 $BOT $TPG --smoke; \
   echo "oplcd_tpg_fl rc $?" >> $LG/chain_d.rc) &
  wait
  echo WAVE1_DONE >> $LG/chain_d.rc
else
  prod $O/cbd_base oplcd_bot_base 150-153 $BOT th_anchor=1.0 &
  prod $O/cbd oplcd_bot_new 154-157 $BOT th_anchor=1.0 &
  (CB=$O/cbd TABLES=$TAB XMX=1g bash $O/fl_pod.sh cmp $O/cbd/scratchpad/gauntlet/L68/rl/oplcd_tpg_fl/fast_msg_u0000.pkl \
   $O/cmp_tpg_cpu.json 158-165 --in-flight 8 --matches 8 --threads 2 > $LG/cmp_tpg_cpu.out 2>&1; echo "cmp rc $?" >> $LG/chain_d.rc) &
  wait
  echo WAVE2_DONE >> $LG/chain_d.rc
fi
