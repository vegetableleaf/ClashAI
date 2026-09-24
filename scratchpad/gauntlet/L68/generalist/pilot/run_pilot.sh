#!/bin/bash
# L68 generalist PILOT drive (top-100 decks x 200 sides). Slot s (port 37031+s) drives chunk_k with k % 4 == s,
# the §5cs.96 recipe (--record-every 20 --record-plays --level 11, default --determinism-every 10).
# Resumable: replay_batch skips tags already in <out>/sN/summary.jsonl, so re-running this script continues.
# Launch: nohup setsid bash run_pilot.sh > $O/run.log 2>&1 < /dev/null &
cd ~/cb
export PYTHONPATH=~/cb:~/cb/research/ext/cr-native-sandbox
O=scratchpad/gauntlet/ext/corpus_gen_pilot
rm -f $O/DONE
for s in 0 1 2 3; do
  (
    for c in $O/crawl/chunk_*; do
      k=$((10#${c##*_}))
      [ $((k % 4)) -eq $s ] || continue
      echo "=== $(date -u +%FT%TZ) $c" >> $O/s$s.log
      python3 research/sandbox_tools/replay_batch.py --crawl $c --tags $c/tags.json --out $O/s$s \
        --port $((37031 + s)) --record-every 20 --record-plays --level 11 >> $O/s$s.log 2>&1
    done
    date -u +%FT%TZ > $O/s$s.done
  ) &
done
wait
date -u +%FT%TZ > $O/DONE
