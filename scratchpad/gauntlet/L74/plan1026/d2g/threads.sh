#!/bin/bash
# threads.sh MAINPID OUT -- every 60 s: per actor (child of MAINPID), cumulative CPU-s per thread group (comm without its
# trailing number), one line per actor: epoch pid group=cpu_s ...
M=$1; OUT=$2; HZ=$(getconf CLK_TCK)
while kill -0 $M 2>/dev/null; do
  for c in $(pgrep -P $M); do
    line=$(for t in /proc/$c/task/*; do printf '%s %s\n' "$(tr ' ' _ < $t/comm 2>/dev/null)" "$(awk '{print $14+$15}' $t/stat 2>/dev/null)"; done |
      awk -v hz=$HZ '{g=$1; sub(/#?[0-9]+$/, "", g); s[g]+=$2} END{for (k in s) if (s[k] > 0) printf "%s=%.1f ", k, s[k]/hz}')
    echo "$(date +%s) $c $line" >> $OUT
  done
  sleep 60
done
