#!/bin/bash
# launch_v2.sh -- 10-25 night: the v2 memory arm mem2_o_s105 on 33458 once D1 s74 is done, then its promotion chain.
# = ctrl_o_s105 (CLXIII recipe, seed 105, 100 updates, critic scale 2.6) + memory v2, init = S3 v2 adapter (33912 /workspace/s3/v2).
set -uo pipefail
cd /c/Users/benpe/ClashBot || exit 1
H=root@157.157.221.29; KEY=~/.ssh/runpod_clashbot; D=scratchpad/gauntlet/L74/memory/promote; mkdir -p $D; LOG=$D/launch_v2.log
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $LOG; }
sshp() { local p=$1; shift; timeout 900 ssh -o BatchMode=yes -o ConnectTimeout=30 -i $KEY -p $p $H "$@"; }
B=/workspace/cb_mem/icebow/data/bench/rl_royale/rlarm_oppD1_deny_s74
until sshp 33458 "[ -f $B/rlarm_oppD1_deny_s74_u0060.pt ] && ! pgrep -f 'cfg/oppD1_deny_s74[.]yaml' > /dev/null"; do sleep 120; done
log "D1 s74 done"
T=$D/v2_mem_best.pt
sshp 33912 "cat /workspace/s3/v2/mem_best.pt" > $T || exit 2
[ "$(sha256sum $T | sed 's/ .*//')" = "$(sshp 33912 'sha256sum /workspace/s3/v2/mem_best.pt' | sed 's/ .*//')" ] || { log "sha mismatch"; exit 2; }
tar czf - pipeline scratchpad/gauntlet/L74/memory/s1c/counter_priors.json scratchpad/gauntlet/L74/memory/s1c/lock_head.json | sshp 33458 "cat > /workspace/pipe_head.tgz"
cat $T | sshp 33458 "mkdir -p /workspace/s3/v2 && cat > /workspace/s3/v2/mem_best.pt"
sshp 33458 'set -e; cd /workspace; [ -d cb_v2 ] || cp -al cb_mem cb_v2; rm -rf cb_v2/pipeline; tar xzf pipe_head.tgz -C cb_v2 --no-same-owner
  sed -i "s#CB=/workspace/cb_stepd;#CB=\${CB:-/workspace/cb_stepd};#" /workspace/exploit/drift_test.sh /workspace/exploit/ev.sh
  C=/workspace/cb_v2/scratchpad/gauntlet/L74/stepd/cfg
  sed -e "s/^seed: 91/seed: 105/" -e "s/^max_updates: 300/max_updates: 100/" -e "s/^shaping_critic_scale: 2.2/shaping_critic_scale: 2.6/" \
      -e "s#^init: .*#init: /workspace/s3/v2/mem_best.pt#" \
      -e "1i # v2 memory arm 10-25 night: ctrl_o_s105 (CLXIII recipe, seed 105) + memory v2 (S1c), init = S3 v2 adapter. ONE change vs ctrl_o_s105." \
      $C/succ48_o_s91.yaml > $C/mem2_o_s105.yaml; echo "memory: v2" >> $C/mem2_o_s105.yaml
  grep -E "^(init|seed|max_updates|shaping_critic_scale|memory)" $C/mem2_o_s105.yaml
  CB=/workspace/cb_v2 setsid nohup bash /workspace/exploit/drift_test.sh mem2_o_s105 100 > /workspace/exploit/drift_mem2_o_s105.out 2>&1 < /dev/null &' >> $LOG 2>&1
log "mem2_o_s105 launched"
exec bash scratchpad/gauntlet/L74/memory/promote_mem.sh mem2_o_s105 33458 CLXV ADAPTIVE
