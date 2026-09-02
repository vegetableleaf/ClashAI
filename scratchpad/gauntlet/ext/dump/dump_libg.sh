#!/system/bin/sh
# Dump every libg.so mapping of the live JniHost probe process from /proc/<pid>/mem (root).
# Runs on the AVD. Output: /data/local/tmp/dump/{maps.txt,libg_<start>_<perms>.bin,index.txt}
OUT=/data/local/tmp/dump
rm -rf $OUT; mkdir -p $OUT
pid=""
i=0
while [ $i -lt 600 ]; do
  pid=$(pgrep -f "^app_process.*JniHost" | head -n 1)
  [ -n "$pid" ] && break
  sleep 0.1; i=$((i+1))
done
echo "pid=$pid" | tee $OUT/index.txt
[ -z "$pid" ] && exit 2
i=0
while [ $i -lt 300 ]; do
  grep -q 'libg.so' /proc/$pid/maps 2>/dev/null && break
  sleep 0.1; i=$((i+1))
done
# jni_on_load (unpack) has finished well before the 5 s headless hold; give it a moment more
sleep ${DUMP_DELAY:-3}
cp /proc/$pid/maps $OUT/maps.txt
grep 'libg.so' /proc/$pid/maps | while read range perms off dev inode path; do
  start=${range%-*}; end=${range#*-}
  s=$((0x$start)); e=$((0x$end)); len=$((e-s))
  f=$OUT/libg_${start}_${perms}.bin
  /data/local/tmp/memdump $pid $start $(printf %x $len) $f 2>&1 | tail -n 1
  echo "$start $end $perms $off $(stat -c %s $f 2>/dev/null)" | tee -a $OUT/index.txt
done
echo done | tee -a $OUT/index.txt
