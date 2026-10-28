#!/bin/bash
# Strip live logs to public frame fields (+ start/end/stop), drop the hidden opp-true-elixir field, gzip.
SRC=/c/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader
OUT=$1
n=0
for f in $SRC/live_play_202610*.jsonl; do
  b=$(basename $f .jsonl); [ -s $OUT/$b.jsonl.gz ] && continue
  grep -E '^\{"event": "(frame|start|end|stop)"' $f \
   | sed -E 's/"opp_elixir_true_EVAL_ONLY": [^,]*, //; s/, "(ents_state|proj|fx|phase2|phase3|cues_degraded|read_us)".*$/}/' \
   | gzip -1 > $OUT/$b.jsonl.gz.tmp && mv $OUT/$b.jsonl.gz.tmp $OUT/$b.jsonl.gz
  n=$((n+1)); [ $((n % 200)) -eq 0 ] && echo "$n $(date +%T)"
done
echo DONE $n
