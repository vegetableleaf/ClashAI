#!/bin/bash
# 10-15 tempo sweep finding: every human-tempo opponent (decide 20-30 ticks, +20 reaction) is far TOO EASY (live F1 u65 53.8%;
# SIM vs gen_v1 T .3 d20 r20 78%, vs E4 d20 r20 74%) -> humans are slower but choose better. Try the imitation generalist
# gen_v32_s0 as the opponent, raw tempo and human tempo, learner F1 u65, seeds 741200 (480 games), live-mirrored pool.
#   strong_opp_pod.sh      (on 45503, checkout cb_s10; results /workspace/results/OPPBEH_S_*; copy back sim_*.json.gz like tempo_sweep_pod.sh)
R=/workspace/results; exec >> $R/strong_opp.log 2>&1; cd /workspace/cb_s10
export CB=/workspace/cb_s10 WORKERS=25 SEEDS=741200 CK=icebow/data/bench/rl_royale/rlarm_gae/rlarm_gae_u0065_grafted.pt
export OPP_CKPT=icebow/data/pipeline/gen_v32_s0/gen_s0.pt OPP_T=.1
for DR in 10:0 20:20; do
  DE=${DR%:*}; RT=${DR#*:}; NAME=S_v32_d${DE}_r${RT}
  if [ $DE = 10 ]; then unset OPP_DE OPP_RT; else export OPP_DE=$DE OPP_RT=$RT; fi
  echo "$(date -u +%T) $NAME"
  NAME=$NAME ISO=/workspace/oppbeh/$NAME bash scratchpad/gauntlet/L74/human/opp_behaviour_pod.sh > $R/oppbeh_$NAME.log 2>&1 || echo "FAILED $NAME"
done
echo "$(date -u +%T) done"; touch $R/STRONG_OPP_DONE
