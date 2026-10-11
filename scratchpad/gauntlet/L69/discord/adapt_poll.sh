#!/bin/bash
# Laptop poller (no Claude calls): when the pod's ADAPT/DONE appears, post ADAPT/SUMMARY.txt to Discord (plain-words formatter).
cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." || exit 1
K="-o BatchMode=yes -o ConnectTimeout=20 -i $HOME/.ssh/runpod_clashbot -p 17497"
M=scratchpad/gauntlet/L69/discord/_adapt_msg.txt
until ssh $K root@64.247.206.76 'test -e /workspace/results/wk/ADAPT/DONE' 2>/dev/null; do sleep 600; done
{ echo '[weekend ADAPT done]'; ssh $K root@64.247.206.76 'cat /workspace/results/wk/ADAPT/SUMMARY.txt'; } > "$M"
icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L69/discord/post.py "$M"
