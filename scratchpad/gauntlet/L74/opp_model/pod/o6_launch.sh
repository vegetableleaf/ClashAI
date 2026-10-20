#!/bin/bash
# O6 arm launch on a step-d pod (= stepd/w6_arm.sh's steps for the opp_model arms; that script only takes W6 arm names).
#   RUN=stepd_l16_proopp_s74 bash /workspace/o6_launch.sh
# Requires: the shipped code (/workspace/in/code.sha) and THIS yaml's real all16 smoke (l16/pod_smoke.sh -> SMOKE_OK).
set -euo pipefail
RUNN=${RUN:?RUN=stepd_l16_proopp_s74|stepd_l16_proopp_s75|stepd_l16_liveopp_s74|stepd_l16_liveopp_s75}
case $RUNN in stepd_l16_proopp_s74|stepd_l16_proopp_s75|stepd_l16_liveopp_s74|stepd_l16_liveopp_s75) ;; *) echo "not an O6 arm: $RUNN"; exit 2;; esac
CB=/workspace/cb_stepd; O=/workspace/stepd
cd $CB
sha256sum -c --quiet /workspace/in/code.sha
grep -q '^league_exploiters:$' scratchpad/gauntlet/L74/stepd/cfg/$RUNN.yaml
grep -q '^live_levels: all16$' scratchpad/gauntlet/L74/stepd/cfg/$RUNN.yaml
[ -f $O/l16_smoke_$RUNN/SMOKE_OK ] || { echo "no SMOKE_OK for $RUNN"; exit 2; }
if pgrep -f 'pipeline[.]rl_royale|gap/gap[.]py|stepd_chain[.]sh' > /dev/null; then echo 'pod busy; no launch'; exit 2; fi
[ ! -e $O/rl_$RUNN/chain.pid ] || { echo "already launched: $O/rl_$RUNN/chain.pid"; exit 2; }
mkdir -p $O/bin $O/rl_$RUNN
cp scratchpad/gauntlet/L74/stepd/stepd_chain.sh $O/bin/stepd_chain.sh
{ echo 'EVAL_LEVELS=all16'; echo "DECODE='--ability-head-decode=sample --crown-log'"; [ -z "${NO36:-}" ] || echo 'NO36=1'; } > $O/GO_$RUNN
RUN=$RUNN setsid nohup flock $O/claim.lock bash $O/bin/stepd_chain.sh > $O/rl_$RUNN/launch.log 2>&1 < /dev/null &
echo $! > $O/rl_$RUNN/chain.pid
echo "O6_ARM_LAUNCHED $RUNN pid=$(cat $O/rl_$RUNN/chain.pid) $(date -u +%FT%TZ) code $(cat /workspace/in/COMMIT 2>/dev/null); log $O/rl_$RUNN/chain.log"
sha256sum scratchpad/gauntlet/L74/stepd/cfg/$RUNN.yaml $O/bin/stepd_chain.sh pipeline/rl_royale.py \
  icebow/data/pipeline/gen_v32_s0/gen_s0.pt icebow/data/bench/rl_royale/rlarm_succ_levels/rlarm_succ_levels_u0065.pt
