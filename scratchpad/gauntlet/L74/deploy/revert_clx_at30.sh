#!/bin/bash
# Owner 10-22 ~13:20: "switch back to CLX once CLXII hits its 30 matches". Waits until 30 ladder result lines exist after
# CLXII went live (overnight.out line 64611 = its first start), then deploys CLX via deploy_ckpt.sh (reader / LIVE_OPTIONS /
# LIVE_RANKED unchanged). Skips if CKPT_OVERRIDE no longer points at CLXII (someone already changed it).
cd /c/Users/benpe/ClashBot || exit 1
F=scratchpad/gauntlet/L70/live/overnight.out; L=scratchpad/gauntlet/L74/deploy/revert_clx_at30.log
until [ "$(tail -n +64611 $F | grep -c '\[ladder\] result:')" -ge 30 ]; do sleep 120; done
n=$(tail -n +64611 $F | grep '\[ladder\] result:' | head -30); w=$(echo "$n" | grep -c WIN); echo "$(date '+%F %T') CLXII 30 results: $w W / $((30 - w)) L" >> $L
grep -q tn_long_e1i_s74_u0100 scratchpad/gauntlet/L70/live/CKPT_OVERRIDE || { echo "CKPT_OVERRIDE changed meanwhile; not deploying" >> $L; exit 0; }
bash scratchpad/gauntlet/L74/deploy/deploy_ckpt.sh icebow/data/models/ICEBOW/ICEBOW_Mark_CLX_PARITY_grafted.pt 5d212358322eb0dd "owner 10-22: back to CLX after CLXII's 30 Ranked matches ($w W / $((30 - w)) L)" >> $L 2>&1
echo "$(date '+%F %T') deploy exit $?" >> $L
