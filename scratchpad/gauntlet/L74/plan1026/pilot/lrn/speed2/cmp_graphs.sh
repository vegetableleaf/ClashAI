#!/bin/bash
# SPEED2 (1): compare.py production vs fast loop with forwards on serve.py GRAPHS (the eager path was checked by LOOP-INT, 16/16)
# on the pilot's B6 warm-start message. usage (pod): cmp_graphs.sh MSG.pkl OUT.json
MSG=$1; OUT=$2
. /workspace/speed2/env.sh; cd $CB || exit 1
FASTLOOP_MEMHASH=1 CRFORGE_XMX=${XMX:-6g} exec timeout ${TMO:-3000} taskset -c $CPUS $PY -u $L/compare.py "$MSG" "$OUT" \
  --device cuda --server graphs --in-flight 8 --matches 8 --threads 4 2>&1 | grep -v "Warning\|self.encoder"
