#!/bin/bash
# Laptop (launch via WMI): once Stage 2 seed A is finished on 13396 (CHAIN_DONE + its u0130 checkpoint), relay that checkpoint
# (the step-d league_exploiters opponent) to the REB pod 19834 and the twin pod 14009; their arm waiters then start.
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"
R=icebow/data/bench/rl_royale/s2_all_il_sA/s2_all_il_sA_u0130.pt
echo "$(date +%T) waiting for 13396 CHAIN_DONE"
until ssh -n $K -p 13396 root@64.247.206.76 "test -e /workspace/s2/CHAIN_DONE && test -f /workspace/cb_tt/$R"; do sleep 120; done
echo "$(date +%T) relay"
bash /c/Users/benpe/ClashBot/scratchpad/gauntlet/L74/stepd/relay_ckpt.sh 64.247.206.76 13396 /workspace/cb_tt/$R $R s2 \
  64.247.206.120 19834 64.247.206.76 14009
echo "$(date +%T) relay exit $?"
