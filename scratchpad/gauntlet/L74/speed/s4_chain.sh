#!/bin/bash
# S4 on pod 30408 (GPU 0): forward rows/s (eager + graphs, then compile), the async server end to end, the slowdown probe.
cd /workspace/cb; export PYTHONPATH=/workspace/cb
INTERP=/workspace/venvf15/bin/python; B=scratchpad/gauntlet/L74/speed/s4_bench.py; O=/workspace/speed/s4; mkdir -p $O
"$INTERP" $B --part forward --modes eager,graphs --out $O/forward_eg.json > $O/forward_eg.log 2>&1
"$INTERP" $B --part slow --out $O/slow.json > $O/slow.log 2>&1
"$INTERP" $B --part server --modes eager,graphs --out $O/server.json > $O/server.log 2>&1
"$INTERP" $B --part forward --modes compile --out $O/forward_c.json > $O/forward_c.log 2>&1
touch $O/S4_DONE
