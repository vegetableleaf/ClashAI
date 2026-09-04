#!/bin/sh
# L46b: same pre-registered probe, same instrument/day, on the m20k snapshot.
export PYTHONHASHSEED=0
cd /c/Users/benpe/ClashBot/icebow
O=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L46
for s in 0 1 2; do
  ../.venv/Scripts/python.exe tools/gate_prior_probe.py C:/Users/benpe/ClashBot/icebow/data/bench/c2r_m20k.pt --seed $s > $O/ge6_c2r_m20k_s$s.txt 2>&1
done
echo PROBES_DONE >> $O/ge6_c2r_m20k_s2.txt
