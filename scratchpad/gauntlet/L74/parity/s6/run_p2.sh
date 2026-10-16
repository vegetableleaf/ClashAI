#!/bin/bash
# the three phase-2 (buffs only, no attack block) owner matches: charges, river/dash jumps, tunnelling, hero cast + taunt
cd /c/Users/benpe/ClashBot
S6=scratchpad/gauntlet/L74/parity/s6
export PARITY_SIM_PATH="${PARITY_SIM_PATH:?}"
export PARITY_ATTACKS="$(pwd -W)/$S6/seeds/attacks.json" PARITY_BUFFS="$(pwd -W)/$S6/seeds/buffs.json" PYTHONHASHSEED=0
for s in live_play_20261016_115958 live_play_20261016_121354 live_play_20261016_122204; do
  python $S6/collect.py $s --out $S6/out
done
echo ALLDONE2
