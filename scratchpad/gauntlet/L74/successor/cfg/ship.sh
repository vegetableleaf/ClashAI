#!/bin/bash
# Laptop: ship the successor overlay to a FACTORIAL pod (it already has /workspace/cb_tt + venvf36 + the factorial's code,
# u250, Mark CXXXVIII grafted and the exploiter from factorial/ship.sh) and stage /workspace/succ. Starts NOTHING.
#   ship.sh build          -> $S/succ_overlay.tar (successor/cfg/* + Mark CXXXVIII RAW u0130 = the arms' init) + manifest
#   ship.sh HOST PORT [Q]  -> extract into /workspace/cb_tt, verify, queue.txt = Q (default queue_<PORT>.txt; never overwrites a live
#                             queue), chain.sh + smoke.sh -> /workspace/succ, touch /workspace/KEEP (owner rule 10-17)
# The code is NOT re-shipped: the arms run the factorial's exact checkout, so the factorial's factor estimates apply to them.
S=/c/Users/benpe/AppData/Local/Temp/claude/C--Users-benpe-ClashBot/f4e7cd66-2122-4134-a1d2-d45291b5bc2a/scratchpad/successor
REPO=/c/Users/benpe/ClashBot; L=scratchpad/gauntlet/L74; RL=icebow/data/bench/rl_royale
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"
set -euo pipefail
if [ "$1" = build ]; then
  cd $REPO; rm -rf $S/stage; mkdir -p $S/stage/$L/successor/cfg $S/stage/$RL/rlarm_gae_cue_u250
  cp $L/successor/cfg/*.yaml $L/successor/cfg/*.py $L/successor/cfg/*.sh $L/successor/cfg/*.txt $L/successor/cfg/decks_hist.json \
    $S/stage/$L/successor/cfg/
  cp $RL/rlarm_gae_cue_u250/rlarm_gae_cue_u250_u0130.pt $S/stage/$RL/rlarm_gae_cue_u250/
  mkdir -p $S/stage/$RL/rlarm_gae_f36_u250    # troops-study arm B grafted (refs.txt ref_f36_u250_B; critic 2 item 3)
  cp /c/Users/benpe/pod_backup_weekend/pod1017_troops/f36/cb_tt/$RL/rlarm_gae_f36_u250/rlarm_gae_f36_u250_u0065_grafted.pt \
    $S/stage/$RL/rlarm_gae_f36_u250/
  ! grep -lU $'\r' $S/stage/$L/successor/cfg/* || { echo "CRLF in a shipped file"; exit 1; }   # -U: Git-Bash grep strips CR otherwise
  (cd $S/stage && tar cf $S/succ_overlay.tar * && find . -type f | sed 's|^\./||' | sort | xargs sha256sum | sed 's/ \*/  /') \
    > $S/succ_manifest.sha
  grep -q "^e02b6a166aee0c6f58f1f22ef5d699265fbeb5f177d0165c7c411ec50c9c859b  $RL/rlarm_gae_cue_u250/rlarm_gae_cue_u250_u0130.pt" $S/succ_manifest.sha
  grep -q "^2ef1142fd9f6ddabed2f56acf9468905492fe425aaeae50af37517d779b633ae  $L/successor/cfg/decks_hist.json" $S/succ_manifest.sha
  grep -q "^4ac98b6bf8590b7f15205bd6537e0188a54317ba8e8b30dcbedeae3021cd79e6  $RL/rlarm_gae_f36_u250/rlarm_gae_f36_u250_u0065_grafted.pt" $S/succ_manifest.sha
  echo "built: $(wc -l < $S/succ_manifest.sha) files, $(du -h $S/succ_overlay.tar | cut -f1)"; exit 0
fi
H=$1; P=$2; Q=${3:-queue_$P.txt}
scp -q $K -P $P $S/succ_overlay.tar $S/succ_manifest.sha root@$H:/workspace/in/
ssh -n $K -p $P root@$H "set -e; touch /workspace/KEEP; cd /workspace/cb_tt && tar xf /workspace/in/succ_overlay.tar --no-same-owner && \
  sha256sum -c --quiet /workspace/in/succ_manifest.sha && echo MANIFEST_OK && \
  ls $RL/rlarm_gae/rlarm_gae_u0250_grafted.pt $RL/rlarm_gae_cue_u250/rlarm_gae_cue_u250_u0130_grafted.pt \
     $RL/rlarm_exploit/rlarm_exploit_u0065.pt icebow/data/rltest/decks_rl.json > /dev/null && echo CKPTS_OK && \
  mkdir -p /workspace/succ && \
  { [ -e /workspace/succ/queue.txt ] && echo 'queue.txt exists: kept' || cp $L/successor/cfg/$Q /workspace/succ/queue.txt; } && \
  for f in chain.sh smoke.sh; do cp $L/successor/cfg/\$f /workspace/succ/.new && mv -f /workspace/succ/.new /workspace/succ/\$f; done && \
  echo \"queue: \$(tr '\n' ' ' < /workspace/succ/queue.txt)\""
