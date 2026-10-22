#!/bin/bash
# branch_trials.sh : owner 10-22. Wait for the tower-branch u40 E4 evals on 157.157.221.29:33572 (ckpt_eval.sh br74_u0040 /
# br75_u0040; 4 seeds x 480 rows each), score each pooled vs CLX (paircmp_pooled.py vs clx_rb rows), keep those NOT clearly worse
# (CI top >= 0), and run trial30.sh on the better one; the other runs only if the first trial reverts. Log: branch_trials.log.
cd /c/Users/benpe/ClashBot || exit 1
K="-o BatchMode=yes -o ConnectTimeout=20 -i $HOME/.ssh/runpod_clashbot"; H=root@157.157.221.29; P=33572
L=scratchpad/gauntlet/L74/deploy/branch_trials.log; log() { echo "$(date '+%F %T') $*" >> $L; }
rows() { ssh -n $K -p $P $H "cat /workspace/ckev/out/$1/e4/$1_*_fin15/*/matches.jsonl 2>/dev/null | wc -l"; }
for t in br74_u0040 br75_u0040; do until [ "$(rows $t)" -ge 1920 ]; do sleep 300; done; log "$t E4 complete"; done
res=""
for t in br74_u0040 br75_u0040; do
  out=$(ssh -n $K -p $P $H "cd /workspace/ckev/out && /workspace/venvf15/bin/python ../paircmp_pooled.py '$t/e4/${t}_{s}_fin15/**/matches.jsonl' 'clx_rb/e4/clx_rb_{s}_fin15/**/matches.jsonl'")
  log "$t vs CLX: $out"
  d=$(echo "$out" | sed -E 's/.*delta=([+-][0-9.]+) pp \[([+-][0-9.]+), ([+-][0-9.]+)\].*/\1 \3/')
  d=${d//+/}; set -- $d; [ -n "${2:-}" ] && awk -v hi=$2 'BEGIN{exit !(hi >= 0)}' && res="$res$1 $t
"
done
order=$(printf '%s' "$res" | sort -rn | awk '{print $2}')
[ -n "$order" ] || { log "no branch passes the SIM pre-filter; CLX stays"; exit 0; }
for t in $order; do
  s=${t:2:2}; R=rlarm_tn_br_tower_s$s; G=${R}_u0040_grafted.pt; D=icebow/data/bench/rl_royale/$R; mkdir -p $D
  scp -q $K -P $P $H:/workspace/cb_stepd/icebow/data/bench/rl_royale/$R/$G $D/ || { log "pull $G failed"; continue; }
  SHA=$(sha256sum $D/$G | cut -c1-16); log "trial $t ($SHA)"
  bash scratchpad/gauntlet/L74/deploy/trial30.sh $D/$G $SHA $t
  grep -q "KEEP $t" scratchpad/gauntlet/L74/deploy/trial30_$t.log && { log "$t KEPT live"; exit 0; }
done
log "no branch kept; CLX live"
