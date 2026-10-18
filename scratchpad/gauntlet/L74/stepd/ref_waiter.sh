#!/bin/bash
# Pod 14009: once the c3_ab chain is finished (/workspace/c3/results_c3_ab/ALL_DONE or DONE, and no rl_royale / gap.py left),
# run stepd_smoke.sh here, then CLIII's fin13 re-score (owner decision 2) = stepd_chain.sh REF mode with NO36=1 (this pod's
# /workspace/fork36 parity checkout breaks the fork36 wheel). Runs UNDER `flock /workspace/stepd/claim.lock` (stop_pod.sh refuses).
#   setsid nohup bash -c 'exec flock /workspace/stepd/claim.lock bash /workspace/stepd/bin/ref_waiter.sh' > /dev/null 2>&1 < /dev/null &
set -uo pipefail
O=/workspace/stepd; C=/workspace/c3/results_c3_ab
log() { echo "[ref] $* $(date -u +%FT%TZ)" >> $O/ref_waiter.log; }
log "waiting (pid $$)"
until { [ -e $C/ALL_DONE ] || [ -e $C/DONE ]; } && ! pgrep -f "pipeline[.]rl_royale|gap/gap[.]py" > /dev/null; do sleep 60; done
log "c3_ab chain finished; smoke"
bash $O/bin/stepd_smoke.sh
[ -e $O/smoke/SMOKE_OK ] || { log "SMOKE FAILED"; exit 3; }
log "CLIII fin13 re-score start"
REF=icebow/data/bench/rl_royale/rlarm_succ_levels/rlarm_succ_levels_u0065_grafted.pt NAME=clIII_fin13 NO36=1 bash $O/bin/stepd_chain.sh
log "ref chain exit $?"
