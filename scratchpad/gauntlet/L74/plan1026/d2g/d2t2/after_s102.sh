#!/bin/bash
# after_s102.sh -- D2-T2: wait for the seed-102 pair-1 runs (old lib) to end, post-process them, then the item-4 chain on
# the CF-CLONE lib (lib_fix) at the original D2-T seed 101.
while kill -0 166680 2>/dev/null || kill -0 166681 2>/dev/null; do sleep 30; done
D=/workspace/d2t2/s102
for e in cf rs; do
  RUN=s102_p1_$e; cp /workspace/d2t/logs/$RUN.log $D/
  /workspace/venvf16/bin/python /workspace/d2/cpu_per_update.py $D/cpu_$RUN.txt /workspace/d2t/cbH/scratchpad/gauntlet/L68/rl/$RUN > $D/upd_$RUN.txt 2>&1
done
CF_LIB=/workspace/d2t2/lib_cfclone exec bash /workspace/d2t/pairs.sh cc /workspace/d2t/cbH /workspace/d2t/buildH 3
