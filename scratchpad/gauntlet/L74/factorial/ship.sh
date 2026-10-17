#!/bin/bash
# Laptop: ship the factorial code + data to a fork36 pod (one that already has /workspace/cb_tt + /workspace/venvf36 from
# troops/setup_troops.sh) and stage /workspace/fact. Does NOT start anything.
#   ship.sh build              build $S/fact_code.tar (git HEAD: pipeline, icebow/src, the L74 dirs the chain uses + the
#                              working-tree factorial/ folder) + $S/fact_ckpt.tar (exploiter u0065, Mark CXXXVIII grafted)
#                              + $S/fact_manifest.sha (sha256 of every shipped file, LF content)
#   ship.sh HOST PORT          copy + extract into /workspace/cb_tt, verify the manifest, queue.txt = queue_<PORT>.txt
#                              (only when /workspace/fact/queue.txt does not exist yet: a live queue is never overwritten)
S=/c/Users/benpe/AppData/Local/Temp/claude/C--Users-benpe-ClashBot/f4e7cd66-2122-4134-a1d2-d45291b5bc2a/scratchpad/factorial
REPO=/c/Users/benpe/ClashBot; L=scratchpad/gauntlet/L74
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"
set -euo pipefail
if [ "$1" = build ]; then
  cd $REPO; rm -rf $S/stage; mkdir -p $S/stage
  git -c core.autocrlf=false archive --format=tar HEAD pipeline icebow/src $L/troops $L/levels $L/mix $L/gap $L/livecal \
    $L/heroiw $L/exploit $L/weekend/graft_generic.py $L/deploy/pod_watchdog.sh | tar x -C $S/stage
  mkdir -p $S/stage/$L/factorial/cfg
  cp $L/factorial/*.sh $L/factorial/*.py $L/factorial/*.txt $L/factorial/design.json $S/stage/$L/factorial/
  cp $L/factorial/cfg/*.yaml $S/stage/$L/factorial/cfg/
  (cd $S/stage && tar cf $S/fact_code.tar *)
  rm -rf $S/ck; mkdir -p $S/ck/icebow/data/bench/rl_royale/rlarm_exploit $S/ck/icebow/data/bench/rl_royale/rlarm_gae_cue_u250
  cp /c/Users/benpe/AppData/Local/Temp/claude/exploit_relay/exploit.pt $S/ck/icebow/data/bench/rl_royale/rlarm_exploit/rlarm_exploit_u0065.pt
  cp icebow/data/bench/rl_royale/rlarm_gae_cue_u250/rlarm_gae_cue_u250_u0130_grafted.pt $S/ck/icebow/data/bench/rl_royale/rlarm_gae_cue_u250/
  (cd $S/ck && tar cf $S/fact_ckpt.tar icebow)
  (cd $S/stage && find . -type f | sed 's|^\./||' | sort | xargs sha256sum; cd $S/ck && find . -type f | sed 's|^\./||' | xargs sha256sum) \
    | sed 's/ \*/  /' > $S/fact_manifest.sha
  grep -q "^5deeb40a7ab379c96b248d33aa94c43986c099e44d1afc5579881d3de93f29c2  icebow/data/bench/rl_royale/rlarm_exploit/" $S/fact_manifest.sha
  grep -q "^0fba110cb883ec1c3ffae0502a90a4bff1ba92b2c8937feef8f039c1590c1d83  icebow/data/bench/rl_royale/rlarm_gae_cue_u250/" $S/fact_manifest.sha
  echo "built: $(wc -l < $S/fact_manifest.sha) files; code $(du -h $S/fact_code.tar | cut -f1), ckpts $(du -h $S/fact_ckpt.tar | cut -f1)"
  exit 0
fi
H=$1; P=$2
scp -q $K -P $P $S/fact_code.tar $S/fact_ckpt.tar $S/fact_manifest.sha root@$H:/workspace/in/
ssh -n $K -p $P root@$H "set -e; cd /workspace/cb_tt && tar xf /workspace/in/fact_code.tar --no-same-owner && \
  tar xf /workspace/in/fact_ckpt.tar --no-same-owner && sha256sum -c --quiet /workspace/in/fact_manifest.sha && echo MANIFEST_OK && \
  grep -E '  icebow/data/bench/rl_royale/rlarm_gae/rlarm_gae_u0250(_grafted)?.pt' /workspace/in/ckpts.sha | sha256sum -c --quiet && \
  echo U250_OK && mkdir -p /workspace/fact && \
  { [ -e /workspace/fact/queue.txt ] && echo 'queue.txt exists: kept' || cp $L/factorial/queue_$P.txt /workspace/fact/queue.txt; } && \
  for f in $L/factorial/chain.sh $L/deploy/pod_watchdog.sh; do cp \$f /workspace/fact/.new && mv -f /workspace/fact/.new /workspace/fact/\$(basename \$f); done && \
  echo \"queue: \$(tr '\n' ' ' < /workspace/fact/queue.txt)\""
