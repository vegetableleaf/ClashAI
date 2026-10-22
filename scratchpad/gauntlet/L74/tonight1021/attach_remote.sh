#!/bin/bash
# attach_remote.sh -- 10-22 (lead, laptop): give the long run (learner on 157.157.221.29:32525) a remote actor server on
# 157.157.221.29:33572 (W16 remote_actors; rows = a single pod with n_actors = local + remote). Steps:
#  1. token (gitignored, never printed) into both pods' cb_stepd/icebow/data/
#  2. 33572: cb_w16 = hard-link copy of cb_stepd (serve.sh runs there); its pipeline hash must equal 32525's
#  3. 33572: server, WORKERS remote actors, fin15 runtime + venvf15
#  4. tunnel 32525 127.0.0.1:5611 -> 33572's server; endpoints file on 32525
# It does NOT restart the learner (that is restart_long.sh, right after a save).
set -euo pipefail
H=157.157.221.29; LP=32525; RP=33572; W=${WORKERS:-48}
K="-o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"; ROOT=/c/Users/benpe/ClashBot
TOK=$ROOT/icebow/data/remote_actors.token
for p in $LP $RP; do ssh $K -p $p root@$H 'umask 077; cat > /workspace/cb_stepd/icebow/data/remote_actors.token' < $TOK; done
ssh $K -p $RP root@$H '[ -d /workspace/cb_w16 ] || cp -al /workspace/cb_stepd /workspace/cb_w16; umask 077; cp /workspace/cb_stepd/icebow/data/remote_actors.token /workspace/cb_w16/icebow/data/'
# the learner's pipeline/ is older than main (W18 edits since): give cb_w16 the LEARNER's exact pipeline/ (rm first, so the
# hard links into cb_stepd are not written through), so the server's hash check passes and cb_stepd stays on main
ssh -n $K -p $LP root@$H 'tar c -C /workspace/cb_stepd pipeline' | ssh $K -p $RP root@$H 'rm -rf /workspace/cb_w16/pipeline && tar x -C /workspace/cb_w16'
HL=$(ssh -n $K -p $LP root@$H 'cd /workspace/cb_stepd && find pipeline -name "*.py" -not -path "*/tests/*" | sort | xargs sha256sum | sha256sum | cut -c1-16')
HR=$(ssh -n $K -p $RP root@$H 'cd /workspace/cb_w16 && find pipeline -name "*.py" -not -path "*/tests/*" | sort | xargs sha256sum | sha256sum | cut -c1-16')
[ "$HL" = "$HR" ] || { echo "PIPELINE HASH MISMATCH learner $HL remote $HR"; exit 3; }
ssh -n $K -p $RP root@$H "sed -i 's/\r$//' /workspace/cb_w16/scratchpad/gauntlet/L74/distrib/serve.sh; WORKERS=$W PY=/workspace/venvf15/bin/python ROYALE_RUNTIME=fin15-linux bash /workspace/cb_w16/scratchpad/gauntlet/L74/distrib/serve.sh"
ssh -n $K -p $LP root@$H 'mkdir -p /workspace/w16; echo 127.0.0.1:5611 > /workspace/cb_stepd/icebow/data/w16_ep.txt'
HOST=root@$H bash $ROOT/scratchpad/gauntlet/L74/distrib/tunnel.sh $LP $RP 5611
echo "ATTACH_READY hash $HL"
