#!/bin/sh
# L46: pre-registered c2r gate read (HANDOFF §6 collapse protocol) -- greedy ledger probe, seeds 0/1/2,
# three ckpts on the SAME instrument the SAME day: gatec2_m10k (init), c2r_m5k, c2r_m10k.
export PYTHONHASHSEED=0
cd /c/Users/benpe/ClashBot/icebow
O=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L46
for ck in gatec2_m10k c2r_m5k c2r_m10k; do
  for s in 0 1 2; do
    ../.venv/Scripts/python.exe tools/gate_prior_probe.py C:/Users/benpe/ClashBot/icebow/data/bench/$ck.pt --seed $s > $O/ge6_${ck}_s$s.txt 2>&1
  done
done
echo PROBES_DONE >> $O/ge6_c2r_m10k_s2.txt
