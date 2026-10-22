#!/bin/bash
# W19: K=0 first-divergence dossiers (diag_night/r3a/div.py: card views, divergences, per-frame live + SIM rows, projectiles) for
# MATCH:T0 pairs, each with its own chunk's exports, in parallel.   bash dossier.sh OUT_DIR 20261017_140050:2929 ...
B=/workspace/w19; C=$B/cb22; PY=/workspace/venvf15/bin/python; O=${1:?}; shift
mkdir -p $O $C/scratchpad/gauntlet/L68
[ -e $C/scratchpad/gauntlet/L68/live_reader ] || ln -s $B/logs $C/scratchpad/gauntlet/L68/live_reader
for mt in "$@"; do
  m=${mt%%:*}; d=$(dirname $(dirname $(ls $B/ch/*/live/live_play_$m.jsonl | head -1)))
  ( cd $O && PYTHONPATH=$C PARITY_SIM_PATH=$B/rsfork_fin15 PARITY_ATTACKS=$d/attacks.json PARITY_BUFFS=$d/buffs.json \
      $PY $C/scratchpad/gauntlet/L74/parity/w19/div.py $O/${mt/:/_}.json $mt > $O/${mt/:/_}.log 2>&1 ) &
done
wait; echo DOSSIER_DONE
