#!/bin/bash
# Human-tempo calibration sweep (owner 10-15 plan: "making opponents play more like human players"; BEHAVIOUR.md: SIM opponents
# play 41% more in 2x and answer our plays within 3 s 48% vs 26% of the time). After WAIT exists, run opp_behaviour_pod.sh on the
# live-mirrored pool, learner = F1 u65 (the live model), seed set 741200 (480 games) per setting, for two opponent policies
# (gen_v1_s0 @ T .3 = the closest existing; E4 @ T .1 = today's CAL c) x tempos (decide every 10 / 20 / 30 ticks, + reaction 0 / 20).
# Results /workspace/results/OPPBEH_<name>/sim_<name>.json.gz; copy back and `opp_behaviour.py report --sim <names>`.
#   tempo_sweep_pod.sh WAIT      (CB = checkout at >= e6d105a with gap.py --opp-decide-every)
set -Eeuo pipefail
W=$1; CB=${CB:-/workspace/clashbot}; R=/workspace/results; mkdir -p $R; exec >> $R/tempo_sweep.log 2>&1
echo "$(date -u +%T) queued after $W"
[ "$W" = none ] || until [ -e $W ]; do sleep 60; done
cd $CB
export CB WORKERS=${WORKERS:-25} SEEDS=741200 CK=icebow/data/bench/rl_royale/rlarm_gae/rlarm_gae_u0065_grafted.pt
for POL in gen3 e4; do
  if [ $POL = gen3 ]; then export OPP_CKPT=icebow/data/pipeline/gen_v1_s0/gen_s0.pt OPP_T=.3; else unset OPP_CKPT; export OPP_T=.1; fi
  for DR in 10:0 20:0 30:0 20:20 30:20; do
    DE=${DR%:*}; RT=${DR#*:}; NAME=T_${POL}_d${DE}_r${RT}
    if [ $DE = 10 ] && [ $RT = 0 ]; then unset OPP_DE OPP_RT; else export OPP_DE=$DE OPP_RT=$RT; fi
    echo "$(date -u +%T) $NAME"
    NAME=$NAME ISO=/workspace/oppbeh/$NAME bash scratchpad/gauntlet/L74/human/opp_behaviour_pod.sh > $R/oppbeh_$NAME.log 2>&1 \
      || echo "FAILED $NAME"
  done
done
touch $R/TEMPO_SWEEP_DONE
echo "$(date -u +%T) done"
