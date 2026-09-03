#!/bin/bash
# L21: wait for the m10k gate snapshot, copy+verify it, run the greedy elixir-bucket probe on 3 seeds (same instrument as m2k/m5k).
cd /c/Users/benpe/ClashBot/icebow
SNAP=data/bench/gate05_m10k.pt; OUT=../scratchpad/gauntlet/L21
until [ -f "$SNAP" ]; do sleep 30; done
s1=$(stat -c %s "$SNAP"); sleep 20; s2=$(stat -c %s "$SNAP")
while [ "$s1" != "$s2" ]; do s1=$s2; sleep 20; s2=$(stat -c %s "$SNAP"); done
cp "$SNAP" "$OUT/gate05_m10k.pt" && cmp "$SNAP" "$OUT/gate05_m10k.pt" && echo "copy verified $(stat -c %s $SNAP) bytes $(date +%H:%M)" > "$OUT/m10k_copy.txt"
for s in 0 1 2; do
  PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tools/gate_prior_probe.py "$SNAP" --seed $s --json "$OUT/m10k_s$s.json" > "$OUT/m10k_s$s.txt" 2>&1
done
echo "DONE $(date +%H:%M)" >> "$OUT/m10k_copy.txt"
