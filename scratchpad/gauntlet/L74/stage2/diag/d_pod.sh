#!/bin/bash
# S2-05(d) ON P5: opp_behaviour.py's live extractor on the 35 newest 13k-band CXXXVIII logs (already on P5 for the S2-04 parse:
# /workspace/s2/audit/main/...) -> 13k-human features, then its report vs the existing gen_v32_s0 SIM set S_v32_d10_r0.
# Isolated root (symlinks into cb_tt), nothing in cb_tt changes.   bash d_pod.sh   -> /workspace/s2/beh/BEHAVIOUR_13k.md
set -euo pipefail
B=/workspace/s2/beh; CB=/workspace/cb_tt; PY=/workspace/venvf36/bin/python; L=scratchpad/gauntlet
rm -rf $B/root; mkdir -p $B/root/$L/L74/human/data $B/root/$L/L74/mix $B/root/$L/L68
for d in pipeline research icebow; do ln -s $CB/$d $B/root/$d; done
ln -s $CB/$L/L74/weekend $B/root/$L/L74/weekend
ln -s /workspace/s2/audit/main/$L/L68/live_reader $B/root/$L/L68/live_reader
cp $CB/$L/L74/human/opp_behaviour.py $B/root/$L/L74/human/
cp $B/sim_S_v32_d10_r0.json.gz $B/root/$L/L74/human/data/
cd $B/root && PYTHONPATH=$B/root $PY -c "
import json, sys; sys.path.insert(0, '$L/L74/weekend'); import archetypes as A
rows = json.load(open('$B/live13k_list_raw.json'))
json.dump([[f, r, sorted({A.canon(c) for c in s})] for f, r, s in rows], open('$L/L74/mix/live_cost_1001.json', 'w'))"
PYTHONPATH=$B/root nice -n 19 $PY $L/L74/human/opp_behaviour.py live > $B/live.log 2>&1
PYTHONPATH=$B/root $PY $L/L74/human/opp_behaviour.py report --sim S_v32_d10_r0 --out $B/BEHAVIOUR_13k.md > $B/report.log 2>&1
echo D_DONE
