#!/bin/bash
# Successor waiter, pod 216.81.245.71:38758 (10-18). Checkout /workspace/succ/cb (fresh: repo_tt + data_rl + ckpts + rsdata +
# fact_code/ckpt + succ overlay, all sha-checked; NOT cb_tt, which carries fast-plays edits). Waits for the cue_ctl chain
# (/workspace/ctl/results/ALL_DONE; /workspace/succ/GO releases it by hand) AND no rl_royale / e1_eval / gap.py / livecal /
# eval6 python, then smoke.sh (cfgcheck + a real rl_royale --smoke of every succ_* in queue.txt) and chain.sh only on SMOKE_OK.
# No pod stop, no watchdog, no deadline timer: /workspace/KEEP stays.
#   setsid nohup bash /workspace/succ/waiter_38758.sh > /dev/null 2>&1 < /dev/null &
F=/workspace/succ; L=$F/waiter.log; export CB=$F/cb
log() { echo "$(date -u +%FT%TZ) $*" >> $L; }
busy() { ps -eo args | grep -v grep | grep -cE "python.*(rl_royale|e1_eval|gap\.py|livecal|eval6)"; }
# idle twice, 60 s apart: a queue of evals on this pod (e.g. combo_queue.sh, no cpu.lock) has ~1 s gaps between its gap.py runs
idle() { { [ -e /workspace/ctl/results/ALL_DONE ] || [ -e $F/GO ]; } && [ "$(busy)" = 0 ] && sleep 60 && [ "$(busy)" = 0 ]; }
log "waiter pid $$ (pgid $(ps -o pgid= $$ | tr -d ' ')): waiting for /workspace/ctl/results/ALL_DONE + idle"
until idle; do sleep 120; done
log "pod free ($([ -e /workspace/ctl/results/ALL_DONE ] && echo ALL_DONE || echo GO)); smoke"
bash $F/smoke.sh
[ -e $F/smoke/SMOKE_OK ] || { log "SMOKE FAILED or refused (see $F/smoke/smoke.log): chain NOT started"; exit 3; }
log "smoke ok; chain"; bash $F/chain.sh; log "chain exit $?"
