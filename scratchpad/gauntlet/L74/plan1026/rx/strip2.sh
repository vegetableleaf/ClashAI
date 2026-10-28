#!/bin/bash
# Logs without frames (list from the pod, one basename per line in $2): decision lines cut after public.raw_bodies.
SRC=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader
OUT=$1
n=0
while read b; do
  [ -s $OUT/$b.dec.gz ] && continue
  grep -E '^\{"event": "decision"' $SRC/$b.jsonl | grep -F '"raw_bodies"' \
   | sed -E 's/, "raw_projectiles".*$/}}/' | gzip -1 > $OUT/$b.dec.gz.tmp && mv $OUT/$b.dec.gz.tmp $OUT/$b.dec.gz
  n=$((n+1)); [ $((n % 200)) -eq 0 ] && echo "$n $(date +%T)"
done < $2
echo DONE $n
