#!/bin/sh
# L50: wait for c2r to cross 30,000 episodes, wait for the NEXT checkpoint save, snapshot, 3-seed probe on
# c2r_m30k AND gatec2_m10k (same instrument, same day: the pre-registered collapse rule's reference).
export PYTHONHASHSEED=0
cd /c/Users/benpe/ClashBot/icebow
O=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L50
LOG=data/bench/c2r_run_20260903.log
PT=data/policy_c2r_20260903.pt
until grep -oE "^\[train-sim-ppo\] [0-9]+ episodes:" $LOG | tail -1 | awk '{exit !($2>=30000)}'; do ping -n 31 127.0.0.1 >/dev/null; done
echo "crossed 30k at $(date)" > $O/wait.txt
M0=$(stat -c %Y $PT)
until [ "$(stat -c %Y $PT)" -gt "$M0" ]; do ping -n 31 127.0.0.1 >/dev/null; done
ping -n 6 127.0.0.1 >/dev/null
cp $PT data/bench/c2r_m30k.pt
echo "snapshot at $(date), log line: $(grep -oE '^\[train-sim-ppo\] [0-9]+ episodes:' $LOG | tail -1)" >> $O/wait.txt
for s in 0 1 2; do
  ../.venv/Scripts/python.exe tools/gate_prior_probe.py C:/Users/benpe/ClashBot/icebow/data/bench/c2r_m30k.pt --seed $s > $O/ge6_c2r_m30k_s$s.txt 2>&1
  ../.venv/Scripts/python.exe tools/gate_prior_probe.py C:/Users/benpe/ClashBot/icebow/data/bench/gatec2_m10k.pt --seed $s > $O/ge6_gatec2_m10k_s$s.txt 2>&1
done
echo PROBES_DONE >> $O/wait.txt
