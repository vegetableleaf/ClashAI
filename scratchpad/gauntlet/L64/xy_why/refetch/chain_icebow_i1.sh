#!/bin/bash
# Chain: icebow re-fetch exit -> i1 tags -> drive i=1 half with v3 flags on 37031 -> fidelity + handedness.
# Also resumes the hogeq re-fetch (24 RateLimited skips) once the icebow fetch is done (same token, sequential).
cd /c/Users/benpe/ClashBot
R=scratchpad/gauntlet/L64/xy_why/refetch
until grep -q ICEBOW_REFETCH_EXIT $R/refetch_icebow2.out; do sleep 60; done
echo "icebow refetch exited $(date -u +%H:%M)"
python $R/i1_tags.py icebow > $R/i1_tags_icebow.out 2>&1; cat $R/i1_tags_icebow.out | cut -c1-300
# hogeq resume in the background (network only)
(cd $R && /c/Users/benpe/clash-replay-scraper/.venv/Scripts/python.exe refetch_i1.py --deck hogeq > refetch_hogeq_resume.out 2>&1; echo HOGEQ_RESUME_EXIT $? >> refetch_hogeq_resume.out) &
mkdir -p scratchpad/gauntlet/ext/corpus_v3_i1r/icebow
research/ext/cr-native-sandbox/.venv/Scripts/python.exe research/sandbox_tools/replay_batch.py --crawl icebow --plays-file plays_ext_i1.csv --tags $R/icebow_i1_tags.json --out scratchpad/gauntlet/ext/corpus_v3_i1r/icebow --record-every 20 --record-plays --determinism-every 10 --port 37031 > $R/drive_icebow_rec.out 2>&1
echo DRIVE_ICEBOW_REC_EXIT $?
python $R/fidelity.py scratchpad/gauntlet/ext/corpus_v3_i1r/icebow/summary.jsonl scratchpad/gauntlet/ext/corpus_v3/icebow/summary.jsonl > $R/fidelity_icebow_full.txt 2>&1
python $R/handedness.py icebow > $R/handedness_icebow_full.txt 2>&1
wait
echo ICEBOW_I1_CHAIN_DONE
