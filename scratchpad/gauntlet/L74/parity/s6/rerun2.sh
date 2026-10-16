#!/bin/bash
# rerun the two logs that were collected before the final extractor (buff totals) landed
cd /c/Users/benpe/ClashBot
S6=scratchpad/gauntlet/L74/parity/s6
until grep -q ALLDONE2 $S6/run_p2.log; do sleep 5; done
export PARITY_SIM_PATH="${PARITY_SIM_PATH:?}"
export PARITY_ATTACKS="$(pwd -W)/$S6/seeds/attacks.json" PARITY_BUFFS="$(pwd -W)/$S6/seeds/buffs.json" PYTHONHASHSEED=0
for s in live_play_20261016_175459 live_play_20261016_162405; do
  rm -rf $S6/out/fights_$s $S6/out/$s.jsonl.gz
  python $S6/collect.py $s --out $S6/out
done
echo ALLDONE3
