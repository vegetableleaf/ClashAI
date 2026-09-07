#!/bin/bash
# L67c: drive the 766 HF exact-icebow replays through the two local engine slots (half each)
cd /c/Users/benpe/ClashBot
PY=research/ext/cr-native-sandbox/.venv/Scripts/python.exe
CR=scratchpad/gauntlet/ext/crawl_hf_icebow
OUT=scratchpad/gauntlet/ext/corpus_v6_new/icebow
mkdir -p "$OUT"
$PY research/sandbox_tools/replay_batch.py --crawl $CR --tags $CR/tags_a.json --out $OUT --record-every 20 --record-plays --port 37031 --determinism-every 0 > scratchpad/gauntlet/L67/drive_v6_a.out 2>&1 &
$PY research/sandbox_tools/replay_batch.py --crawl $CR --tags $CR/tags_b.json --out $OUT --record-every 20 --record-plays --port 37032 --determinism-every 0 > scratchpad/gauntlet/L67/drive_v6_b.out 2>&1 &
wait
echo DRIVE_DONE >> scratchpad/gauntlet/L67/drive_v6_a.out
