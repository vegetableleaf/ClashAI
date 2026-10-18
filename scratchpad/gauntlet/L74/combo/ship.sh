#!/bin/bash
# Laptop: ship the combo code + Mark CXXXVIII (raw init + grafted) to a fork36 pod that already has /workspace/cb_tt +
# /workspace/venvf36 (troops/setup_troops.sh; every factorial pod has them) and stage /workspace/combo. Starts NOTHING.
#   ship.sh build         $S/combo_code.tar = git HEAD (pipeline, icebow/src, the L74 dirs the chain uses) OVERLAID with the
#                         WORKING-TREE combo files (pipeline/spell_value.py, rl_royale.py, royale_env.py, e1_eval.py,
#                         search_s0.py, tests/test_spell_value.py, L74/combo/) -- uncommitted until the lead commits; rebuild
#                         after any commit -- + $S/combo_ckpt.tar (Mark CXXXVIII u0130 raw + grafted) + $S/combo_manifest.sha
#   ship.sh HOST PORT     copy + extract into /workspace/cb_tt, verify the manifest, /workspace/combo/queue.txt =
#                         combo/queue_<PORT>.txt (only when no queue.txt exists: a live queue is never overwritten), chain.sh
S=/c/Users/benpe/AppData/Local/Temp/claude/C--Users-benpe-ClashBot/f4e7cd66-2122-4134-a1d2-d45291b5bc2a/scratchpad/combo_ship
REPO=/c/Users/benpe/ClashBot; L=scratchpad/gauntlet/L74
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"
WT="pipeline/spell_value.py pipeline/rl_royale.py pipeline/royale_env.py pipeline/e1_eval.py pipeline/search_s0.py pipeline/tests/test_spell_value.py"
CK=icebow/data/bench/rl_royale/rlarm_gae_cue_u250
set -euo pipefail
if [ "$1" = build ]; then
  cd $REPO; rm -rf $S/stage $S/ck; mkdir -p $S/stage $S/ck/$CK
  git -c core.autocrlf=false archive --format=tar HEAD pipeline icebow/src $L/troops $L/levels $L/mix $L/gap $L/livecal \
    $L/heroiw $L/exploit $L/fastplays $L/weekend/graft_generic.py | tar x -C $S/stage
  for f in $WT; do mkdir -p $S/stage/$(dirname $f); tr -d '\r' < $f > $S/stage/$f; done
  mkdir -p $S/stage/$L/combo/cfg
  for f in $L/combo/*.sh $L/combo/*.py $L/combo/*.txt $L/combo/cfg/*.yaml; do tr -d '\r' < $f > $S/stage/$f; done
  mkdir -p $S/stage/$L/combo/head                                    # smoke.sh's off_old twin: the HEAD modules
  for f in rl_royale royale_env e1_eval search_s0; do git show HEAD:pipeline/$f.py | tr -d '\r' > $S/stage/$L/combo/head/$f.py; done
  (cd $S/stage && tar cf $S/combo_code.tar *)
  cp $CK/rlarm_gae_cue_u250_u0130.pt $CK/rlarm_gae_cue_u250_u0130_grafted.pt $S/ck/$CK/
  (cd $S/ck && tar cf $S/combo_ckpt.tar icebow)
  (cd $S/stage && find . -type f | sed 's|^\./||' | sort | xargs sha256sum; cd $S/ck && find . -type f | sed 's|^\./||' | xargs sha256sum) \
    | sed 's/ \*/  /' > $S/combo_manifest.sha
  grep -q "^0fba110cb883ec1c3ffae0502a90a4bff1ba92b2c8937feef8f039c1590c1d83  $CK/rlarm_gae_cue_u250_u0130_grafted.pt" $S/combo_manifest.sha
  grep -q "^e02b6a166aee" $S/combo_manifest.sha
  echo "built: $(wc -l < $S/combo_manifest.sha) files; code $(du -h $S/combo_code.tar | cut -f1), ckpts $(du -h $S/combo_ckpt.tar | cut -f1)"
  for f in $WT; do grep "  $f\$" $S/combo_manifest.sha | cut -c1-16 | tr '\n' ' '; echo " $f"; done
  other=$(git status --short pipeline | awk '{print $2}' | grep '\.py$' | grep -vxF "$(echo $WT | tr ' ' '\n')" || true)
  [ -z "$other" ] || echo "WARNING: uncommitted pipeline files shipped at their HEAD version (commit first if they belong): $other"
  exit 0
fi
H=$1; P=$2; C=${CBDIR:-/workspace/cb_tt}
# CBDIR (default /workspace/cb_tt): a SEPARATE checkout on a shared pod (P3: CBDIR=/workspace/cb_combo) = a hard-link copy of
# /workspace/cb_tt (data shared, no extra disk) whose code dirs are removed and re-extracted from the tar (never written through
# a link); chain.sh / smoke.sh then run with CB=$CBDIR.
ssh -n $K -p $P root@$H "mkdir -p /workspace/in /workspace/combo"
scp -q $K -P $P $S/combo_code.tar $S/combo_ckpt.tar $S/combo_manifest.sha root@$H:/workspace/in/
ssh -n $K -p $P root@$H "set -e
  if [ $C != /workspace/cb_tt ] && [ ! -d $C ]; then
    cp -al /workspace/cb_tt $C && rm -rf $C/pipeline $C/icebow/src $C/scratchpad/gauntlet/L74 && echo LINKED_COPY $C
  fi
  cd $C && tar xf /workspace/in/combo_code.tar --no-same-owner && tar xf /workspace/in/combo_ckpt.tar --no-same-owner
  sha256sum -c --quiet /workspace/in/combo_manifest.sha && echo MANIFEST_OK
  if [ -e /workspace/combo/queue.txt ]; then echo 'queue.txt exists: kept'
  elif [ -e $L/combo/queue_$P.txt ]; then cp $L/combo/queue_$P.txt /workspace/combo/queue.txt; else echo 'no queue for this port'; fi
  cp $L/combo/chain.sh /workspace/combo/.new && mv -f /workspace/combo/.new /workspace/combo/chain.sh
  echo queue: \$(cat /workspace/combo/queue.txt 2>/dev/null)"
