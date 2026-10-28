#!/bin/bash
# cpusample.sh MAINPID OUT -- every 20 s: epoch, main process cpu-s, sum of live children's cpu-s (utime+stime), n children
M=$1; OUT=$2; HZ=$(getconf CLK_TCK)
while kill -0 $M 2>/dev/null; do
  m=$(awk -v hz=$HZ '{print ($14+$15)/hz}' /proc/$M/stat 2>/dev/null)
  k=$(for c in $(pgrep -P $M); do cat /proc/$c/stat 2>/dev/null; echo; done | awk -v hz=$HZ 'NF>15{s+=($14+$15)/hz; n++} END{printf "%.2f %d", s, n}')
  echo "$(date +%s) $m $k" >> $OUT
  sleep 20
done
