#!/bin/bash
# launch_tc.sh -- 10-25 night: memtc_o_s105 on 33522 once D1 s75 is done = mem_o_s105 + shaping tower_crown (credits tower damage,
# e.g. a chip Rocket, when it lands; potential-based). Diagnoses which x-arm term re-learned the leak AND tests a Rocket-credit
# lever on the memory model. Critic scale 3.5 (the bound with tower_crown on; as x_s101). REPORT ONLY: not in the live permission.
set -uo pipefail
cd /c/Users/benpe/ClashBot || exit 1
H=root@157.157.221.29; KEY=~/.ssh/runpod_clashbot; D=scratchpad/gauntlet/L74/memory/promote; mkdir -p $D; LOG=$D/launch_tc.log
log() { echo "$(date -u +%FT%TZ) $*" | tee -a $LOG; }
sshp() { local p=$1; shift; timeout 900 ssh -o BatchMode=yes -o ConnectTimeout=30 -i $KEY -p $p $H "$@"; }
B=/workspace/cb_mem/icebow/data/bench/rl_royale/rlarm_oppD1_deny_s75
until sshp 33522 "[ -f $B/rlarm_oppD1_deny_s75_u0060.pt ] && ! pgrep -f 'cfg/oppD1_deny_s75[.]yaml' > /dev/null"; do sleep 120; done
log "D1 s75 done"
sshp 33912 "cat /workspace/s3/v1ctrl/mem_best.pt" | sshp 33522 "mkdir -p /workspace/s3/v1ctrl && cat > /workspace/s3/v1ctrl/mem_best.pt"
sshp 33912 "cat /workspace/cb_mem/scratchpad/gauntlet/L74/stepd/cfg/mem_o_s105.yaml" | sed -e "s/^shaping: none/shaping: tower_crown/" \
  -e "s/^shaping_critic_scale: 2.6/shaping_critic_scale: 3.5/" -e "1i # memtc_o_s105: mem_o_s105 + shaping tower_crown (critic scale 3.5 forced by the bound)." \
  | sshp 33522 "cat > /workspace/cb_gate/scratchpad/gauntlet/L74/stepd/cfg/memtc_o_s105.yaml"
sshp 33522 'sed -i "s#CB=/workspace/cb_stepd;#CB=\${CB:-/workspace/cb_stepd};#" /workspace/exploit/drift_test.sh /workspace/exploit/ev.sh
  grep -E "^(init|seed|shaping|shaping_critic_scale|memory|max_updates)" /workspace/cb_gate/scratchpad/gauntlet/L74/stepd/cfg/memtc_o_s105.yaml
  CB=/workspace/cb_gate setsid nohup bash /workspace/exploit/drift_test.sh memtc_o_s105 100 > /workspace/exploit/drift_memtc_o_s105.out 2>&1 < /dev/null &' >> $LOG 2>&1
log "memtc_o_s105 launched"
