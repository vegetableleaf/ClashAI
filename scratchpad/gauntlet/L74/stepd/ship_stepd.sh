#!/bin/bash
# Laptop: ship the step-d code + data to a pod that already has /workspace/cb_tt + /workspace/venvf36 (combo/newpod.sh or
# any factorial / combo pod). Starts NOTHING.
#   ship_stepd.sh build      -> $S/stepd_code.tar = git HEAD (pipeline, icebow/src, L74, L73, L69/gen_v2, L70/gen_v31) OVERLAID
#                               with the WORKING-TREE pipeline/*.py + tests + L74/stepd (uncommitted until the lead commits);
#                               $S/stepd_data.tar = gen_dataset_v32_fv5.npz, gen_v32_s0, public_context_v32_w4, the 5 crawl
#                               dirs' battles + plays CSVs, CLIII raw + grafted; $S/stepd_manifest.sha (both)
#   ship_stepd.sh code       -> rebuild only stepd_code.tar (+ manifest)
#   ship_stepd.sh HOST PORT [data] -> /workspace/cb_stepd = a hard-link copy of /workspace/cb_tt whose code dirs are removed and
#                               re-extracted from the tar (never written through a link); "data" also ships stepd_data.tar
S=/c/Users/benpe/AppData/Local/Temp/claude/stepd_ship
REPO=/c/Users/benpe/ClashBot; L=scratchpad/gauntlet/L74
K="-o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -o StrictHostKeyChecking=no -i $HOME/.ssh/runpod_clashbot"
DIRS="pipeline icebow/src $L scratchpad/gauntlet/L73 scratchpad/gauntlet/L69/gen_v2 scratchpad/gauntlet/L70/gen_v31"
CR="scratchpad/gauntlet/L68/generalist/pilot/crawl scratchpad/gauntlet/ext/crawl_hf_icebow scratchpad/gauntlet/ext/crawl_hf_hogeq icebow/data/royaleapi/crawl2 hogeq/data/royaleapi/crawl2"
SL=icebow/data/bench/rl_royale/rlarm_succ_levels
set -euo pipefail
cd $REPO
if [ "$1" = build ] || [ "$1" = code ]; then
  mkdir -p $S; rm -rf $S/stage; mkdir -p $S/stage
  git -c core.autocrlf=false archive --format=tar HEAD $DIRS | tar x -C $S/stage
  for f in $(git ls-files -m -o --exclude-standard pipeline $L/stepd $L/pro2 | grep -E '\.(py|sh|md|json|yaml)$' | grep -v '/tests/gen_v3/'); do
    mkdir -p $S/stage/$(dirname $f); tr -d '\r' < $f > $S/stage/$f
  done
  (cd $S/stage && tar cf $S/stepd_code.tar * && find . -type f | sed 's|^\./||' | sort | xargs sha256sum | sed 's/ \*/  /') > $S/code.sha
  echo "code: $(wc -l < $S/code.sha) files, $(du -h $S/stepd_code.tar | cut -f1)"
fi
if [ "$1" = build ]; then
  rm -rf $S/dstage; mkdir -p $S/dstage/$SL
  F="icebow/data/pipeline/gen_dataset_v32_fv5.npz icebow/data/pipeline/gen_v32_s0/gen_s0.pt icebow/data/pipeline/gen_v32_s0/final_gen_s0.json"
  F="$F $(ls .foreman/codex_autopilot/runs/public_context_v32_w4/*)"
  for d in $CR; do F="$F $(ls $d/battles.csv $d/plays_ext_i1.csv $d/plays_ext.csv $d/plays.csv 2>/dev/null || true)"; done
  tar cf $S/stepd_data.tar $F
  cp /c/Users/benpe/pod_backup_weekend/pod1017_successor/succ_levels/rlarm_succ_levels_u0065{,_grafted}.pt $S/dstage/$SL/
  (cd $S/dstage && tar rf $S/stepd_data.tar $SL)
  { sha256sum $F; (cd $S/dstage && sha256sum $SL/*); } | sed 's/ \*/  /' > $S/data.sha
  grep -q "^29ecefa9" $S/data.sha; grep -q "^61011b6c" $S/data.sha; grep -q "^05d42da7" $S/data.sha; grep -q "^edc82ada" $S/data.sha
  echo "data: $(wc -l < $S/data.sha) files, $(du -h $S/stepd_data.tar | cut -f1)"
fi
[ "$1" = build ] || [ "$1" = code ] && exit 0
H=$1; P=$2; C=/workspace/cb_stepd
ssh -n $K -p $P root@$H "mkdir -p /workspace/in /workspace/stepd"
scp -q $K -P $P $S/stepd_code.tar $S/code.sha root@$H:/workspace/in/
[ "${3:-}" = data ] && scp -q $K -P $P $S/stepd_data.tar $S/data.sha root@$H:/workspace/in/
ssh -n $K -p $P root@$H "set -e; touch /workspace/KEEP
  [ -d /workspace/cb_tt/pipeline ] || { echo 'no /workspace/cb_tt'; exit 1; }
  if [ ! -d $C ]; then cp -al /workspace/cb_tt $C && echo LINKED_COPY; fi
  cd $C; rm -rf $DIRS; tar xf /workspace/in/stepd_code.tar --no-same-owner && sha256sum -c --quiet /workspace/in/code.sha && echo CODE_OK
  if [ '${3:-}' = data ]; then tar xf /workspace/in/stepd_data.tar --no-same-owner && sha256sum -c --quiet /workspace/in/data.sha && echo DATA_OK && rm /workspace/in/stepd_data.tar; fi"
