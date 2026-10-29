#!/bin/bash
# OPP-LEARN-D timing_pg smokes with micro_batch 256 (prod + fast loop in parallel), then compare on the fast u0000 msg.
set -f
O=/workspace/oplc; LG=$O/logsd; L=/workspace/crforge_main/fe364ceb/plain; TAB=/workspace/crforge_cache/tables/16.635.3
BOT=scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_bot_smoke.yaml
TPG="th_anchor=10.0 timing_pg=true freeze_heads=[ability] micro_batch=256"
R=${R:-2}
(cd $O/cbd && env PYTHONPATH=$O/cbd ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 RL_BATCH_SHA=1 ROYALE_ENGINE=crforge CRFORGE_LIB=$L/lib \
  CRFORGE_TABLES=$TAB CRFORGE_FACADE_BUILD=$O/fac_cbd CRFORGE_XMX=1g JAVA_TOOL_OPTIONS="-XX:+UseSerialGC -XX:ActiveProcessorCount=1" \
  taskset -c 158-161 timeout 7200 /workspace/venvf16/bin/python -u -m pipeline.rl_royale --run oplcd_tpg_prod$R --config $BOT --smoke \
  actor_device=cpu learner_device=cpu $TPG > $LG/oplcd_tpg_prod$R.log 2>&1; echo "oplcd_tpg_prod$R rc $?" >> $LG/smk_d.rc) &
(CB=$O/cbd TABLES=$TAB LOGS=$LG DUMP=1 XMX=1g bash $O/fl_pod.sh fast oplcd_tpg_fl$R 162-169 $BOT $TPG --smoke; \
  echo "oplcd_tpg_fl$R rc $?" >> $LG/smk_d.rc) &
wait
CB=$O/cbd TABLES=$TAB XMX=1g bash $O/fl_pod.sh cmp $O/cbd/scratchpad/gauntlet/L68/rl/oplcd_tpg_fl$R/fast_msg_u0000.pkl \
  $O/cmp_tpg_cpu$R.json 158-165 --in-flight 8 --matches 8 --threads 2 > $LG/cmp_tpg_cpu$R.out 2>&1; echo "cmp$R rc $?" >> $LG/smk_d.rc
echo SMK_DONE >> $LG/smk_d.rc
