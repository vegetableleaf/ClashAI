#!/bin/bash
# L74 W6 (10-20): launch ONE crown-term arm (stepd_l16_lead | stepd_l16_redirect | stepd_l16_tornado = stepd_l16_s74 + one
# key, seed 74) through the step-d chain. Starts nothing on its own; the LEAD runs it, on a pod the lead assigns, after the
# L16 verdict. Run ON the pod (an L16 pod: /workspace/cb_stepd, venvf13, the s74 init and data already there):
#   RUN=stepd_l16_lead bash /workspace/cb_stepd/scratchpad/gauntlet/L74/stepd/w6_arm.sh        (NO36=1 ... on 14009)
# Before it, on the laptop: ship the code FROM THE COMMIT (ship_stepd.sh "code" overlays the WORKING TREE's pipeline/*.py,
# which carries unrelated uncommitted edits):
#   S=/c/Users/benpe/AppData/Local/Temp/claude/stepd_ship; rm -rf $S/stage && mkdir -p $S/stage
#   git -c core.autocrlf=false archive --format=tar HEAD pipeline icebow/src scratchpad/gauntlet/L74 scratchpad/gauntlet/L73 \
#     scratchpad/gauntlet/L69/gen_v2 scratchpad/gauntlet/L70/gen_v31 | tar x -C $S/stage
#   (cd $S/stage && tar cf $S/stepd_code.tar * && find . -type f | sed 's|^\./||' | sort | xargs sha256sum | sed 's/ \*/  /') > $S/code.sha
#   bash scratchpad/gauntlet/L74/stepd/ship_stepd.sh HOST PORT                                  (-> CODE_OK)
# Steps here: refuse on a busy pod; the real all16 smoke of THIS yaml (l16/pod_smoke.sh: --smoke critic_warmup_updates=1
# -> SMOKE PASS); GO file = EVAL_LEVELS=all16 + DECODE with --crown-log (the eval rows carry the crown slices readout.py
# prints; the tracker never changes play); the chain under claim.lock (130 updates ~5.5 h, then the all16 evals).
# The crown BASELINE (the same recipe and seed without a term) is stepd_l16_s74's u130 re-scored with --crown-log, once, on
# the pod that trained it:
#   cd /workspace/cb_stepd && REF=icebow/data/bench/rl_royale/rlarm_stepd_l16_s74/rlarm_stepd_l16_s74_u0130_grafted.pt \
#     NAME=stepd_l16_s74_crown EVAL_LEVELS=all16 NO36=1 DECODE='--ability-head-decode=sample --crown-log' \
#     setsid nohup flock /workspace/stepd/claim.lock bash /workspace/stepd/bin/stepd_chain.sh > /dev/null 2>&1 < /dev/null &
#   (its win/loss rows must equal stepd_l16_s74's own: a free real-engine check that --crown-log changes nothing)
set -euo pipefail
RUNN=${RUN:?RUN=stepd_l16_lead|stepd_l16_redirect|stepd_l16_tornado}
case $RUNN in stepd_l16_lead|stepd_l16_redirect|stepd_l16_tornado) ;; *) echo "not a W6 arm: $RUNN"; exit 2;; esac
CB=/workspace/cb_stepd; O=/workspace/stepd
cd $CB
sha256sum -c --quiet /workspace/in/code.sha
grep -q -E '^(lead_protect: on|princess_redirect: (penalty|potential)|tornado_king_penalty: on)$' scratchpad/gauntlet/L74/stepd/cfg/$RUNN.yaml
if pgrep -f 'pipeline[.]rl_royale|gap/gap[.]py|stepd_chain[.]sh' > /dev/null; then echo 'pod busy; no launch'; exit 2; fi
[ ! -e $O/rl_$RUNN/chain.pid ] || { echo "already launched: $O/rl_$RUNN/chain.pid"; exit 2; }
RUN=$RUNN bash scratchpad/gauntlet/L74/l16/pod_smoke.sh                       # exits non-zero unless SMOKE PASS
mkdir -p $O/bin $O/rl_$RUNN
cp scratchpad/gauntlet/L74/stepd/stepd_chain.sh $O/bin/stepd_chain.sh
{ echo 'EVAL_LEVELS=all16'; echo "DECODE='--ability-head-decode=sample --crown-log'"; [ -z "${NO36:-}" ] || echo 'NO36=1'; } > $O/GO_$RUNN
RUN=$RUNN setsid nohup flock $O/claim.lock bash $O/bin/stepd_chain.sh > $O/rl_$RUNN/launch.log 2>&1 < /dev/null &
echo $! > $O/rl_$RUNN/chain.pid
echo "W6_ARM_LAUNCHED $RUNN pid=$(cat $O/rl_$RUNN/chain.pid) $(date -u +%FT%TZ); log $O/rl_$RUNN/chain.log"
