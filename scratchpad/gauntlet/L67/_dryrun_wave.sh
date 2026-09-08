cd /c/Users/benpe/ClashBot
P=./icebow/.venv/Scripts/python.exe
for S in 20260815_222309 20260804_192006; do
  $P scratchpad/gauntlet/L67/student_dryrun.py icebow/data/sessions/$S \
     --ckpt icebow/data/pipeline/s1_icebow_v6lat_s0.pt \
     --out scratchpad/gauntlet/L67/dryrun_${S}.jsonl --every 12 --limit 400 \
     >> scratchpad/gauntlet/L67/dryrun_wave.out 2>&1
done
echo DRYRUN_WAVE_DONE >> scratchpad/gauntlet/L67/dryrun_wave.out
