#!/bin/bash
# SPEED2 (2): mem_probe.py on one pilot actor message at several -Xmx (and GC) settings: one producer of M matches x
# 4 threads (J jobs per wave; EXTRA = more mem_probe args, e.g. "--waves 3 --serve graphs").
# usage (pod): [M=16 J=16 EXTRA=...] memsweep.sh MSG.pkl TAG XMX[:GCFLAGS] ...
MSG=$1; TAG=$2; shift 2
. /workspace/speed2/env.sh; cd $CB || exit 1
O=/workspace/speed2/out/mem; mkdir -p $O
for spec in "$@"; do
  x=${spec%%:*}; gc=; [ "$spec" != "$x" ] && gc=${spec#*:}
  n=${TAG}_xmx$x$( [ -n "$gc" ] && echo _gc)
  CRFORGE_XMX=$x JAVA_TOOL_OPTIONS="-XX:NativeMemoryTracking=summary $gc" taskset -c $CPUS timeout 3000 $PY -u \
    scratchpad/gauntlet/L74/plan1026/pilot/lrn/speed2/mem_probe.py $MSG $O/$n.json --matches ${M:-16} --threads 4 \
    --jobs ${J:-16} $EXTRA > $O/$n.log 2>&1
done
touch $O/DONE_$TAG
