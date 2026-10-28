#!/usr/bin/env bash
set -u
date -u
ps -p 2007780 -o pid,etime,args
P=/dev/shm/f1fix_main_sync_20261028_dev
E='UnsupportedClassVersionError|NoSuchMethodError|NoClassDefFoundError|LinkageError|IncompatibleClassChangeError'
if test -f "$P.log"; then
 echo 'dev log tail'; tail -10 "$P.log"
 echo 'dev log linkage errors'; grep -n -m1 -A29 -E "$E" "$P.log" || true
fi
for f in $(find "$P" -maxdepth 2 -type f -name 'result*' | sort | head -5); do
 echo "result $f"; grep -n -m1 -A29 -E "$E" "$f" || true
done
for f in /workspace/pilot/f1fix/runs/main_sync_20261028_{dev,fresh1}.log; do
 if test -f "$f" && grep -q Traceback "$f"; then echo "traceback $f"; tail -40 "$f"; fi
done
