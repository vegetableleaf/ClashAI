cd /c/Users/benpe/ClashBot/icebow
OUT=../scratchpad/gauntlet/L22
declare -A CK=( [m2k]=../scratchpad/gauntlet/L11/gate05_m2k.pt [m5k]=../scratchpad/gauntlet/L16/gate05_m5k.pt [m10k]=../scratchpad/gauntlet/L21/gate05_m10k.pt )
for mode in sampled greedy; do
  for k in m2k m5k m10k; do
    for s in 1 2 3; do
      PYTHONHASHSEED=0 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe $OUT/term_ledger.py "${CK[$k]}" 24 $s "$OUT/led_${k}_${mode}_s$s.json" $mode > "$OUT/led_${k}_${mode}_s$s.txt" 2>&1 &
    done
  done
  wait
done
echo "GRID DONE $(date +%H:%M)" > $OUT/grid_done.txt
