#!/bin/bash
# S6 runs: baseline (HEAD extractor) on 175459, then the current extractor on all five logs. Sequential, one process.
cd /c/Users/benpe/ClashBot
S6=scratchpad/gauntlet/L74/parity/s6
export PARITY_SIM_PATH="${PARITY_SIM_PATH:?set PARITY_SIM_PATH to the unpacked royalesim 0.1.35 dir}"
export PARITY_ATTACKS="$(pwd -W)/$S6/seeds/attacks.json" PARITY_BUFFS="$(pwd -W)/$S6/seeds/buffs.json" PYTHONHASHSEED=0
for s in live_play_20261016_175459 live_play_20261016_162405 live_play_20261016_133158 live_play_20261016_134401 live_play_20261016_135037; do
  python $S6/collect.py $s --out $S6/out
done
echo ALLDONE
