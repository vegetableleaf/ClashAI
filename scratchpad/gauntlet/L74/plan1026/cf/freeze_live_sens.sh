#!/usr/bin/env bash
# sequential sensitivity runs: base-only mode on the 220 records, one tables variant after another
for v in cube4000b slow0 radius3000; do
  rm -f /dev/shm/fl_sens_$v.jsonl
  TAB=/dev/shm/fl_tabs_$v SME_THREADS=2 bash /dev/shm/freeze_live_env.sh python3 /dev/shm/freeze_live_cf.py /dev/shm/fl_list.jsonl /dev/shm/fl_sens_$v.jsonl 6 base > /dev/shm/fl_sens_$v.log 2>&1
  echo done $v >> /dev/shm/fl_sens_progress.txt
done
