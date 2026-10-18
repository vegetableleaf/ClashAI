#!/bin/bash
# RL pod: start one step-d arm when its pod and inputs are ready. Runs UNDER `flock /workspace/stepd/claim.lock`, so
# deploy/stop_pod.sh (which refuses while any flock process lives) cannot release the pod in the idle gap before training.
#   RUN=stepd_ctrl setsid nohup flock /workspace/stepd/claim.lock bash /workspace/stepd/bin/arm_waiter.sh > /dev/null 2>&1 < /dev/null &
# Waits for: Stage 2's /workspace/s2/CHAIN_DONE (if this pod ran Stage 2) and no rl_royale / gap.py left; the arm's init + the
# league_exploiters checkpoint inside /workspace/cb_stepd (linked from cb_tt when this pod trained it, else shipped by the lead);
# a GO file /workspace/stepd/GO_<RUN> (written by the lead once the arm's yaml is final: ability head / spell reward decided).
# Then: stepd_smoke.sh on THIS pod (SMOKE_OK), then stepd_chain.sh RUN=<RUN>. No pod stop, no watchdog, no deadline.
set -uo pipefail
RUNN=${RUN:?RUN=stepd_ctrl|stepd_reb|stepd_rebc3}; O=/workspace/stepd; CB=/workspace/cb_stepd
RL=icebow/data/bench/rl_royale; S2=$RL/s2_all_il_sA/s2_all_il_sA_u0130.pt
log() { echo "[arm $RUNN] $* $(date -u +%FT%TZ)" >> $O/arm_waiter.log; }
log "waiting (pid $$)"
until { [ ! -d /workspace/s2 ] || [ -e /workspace/s2/CHAIN_DONE ]; } && ! pgrep -f "pipeline[.]rl_royale|gap/gap[.]py" > /dev/null; do sleep 60; done
log "pod free"
cd $CB
Y=scratchpad/gauntlet/L74/stepd/cfg/$RUNN.yaml
until [ -e $O/GO_$RUNN ]; do sleep 60; done
[ -f $S2 ] || { [ -f /workspace/cb_tt/$S2 ] && mkdir -p $(dirname $S2) && ln -f /workspace/cb_tt/$S2 $S2 && log "linked $S2"; }
INIT=$(awk '/^init: / {print $2; exit}' $Y)   # top-level key only: league_mix also has an indented "init:"
grep -q '^league_exploiters:' $Y || S2=$INIT      # an arm without the Stage 2 opponents (stepd_ctrl_nos2) needs only its init
until [ -f $S2 ] && [ -f $INIT ]; do sleep 60; done
log "inputs ok: init $INIT ($(sha256sum $INIT | cut -c1-16)), exploiter $S2 ($(sha256sum $S2 | cut -c1-16))"
bash $O/bin/stepd_smoke.sh
[ -e $O/smoke/SMOKE_OK ] || { log "SMOKE FAILED: not started"; exit 3; }
log "smoke ok; chain start"
RUN=$RUNN bash $O/bin/stepd_chain.sh
log "chain exit $?"
