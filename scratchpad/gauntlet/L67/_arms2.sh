#!/usr/bin/env bash
# L67h confirmation: the DISJOINT seed slice. Project rule -- a headline number is re-run on seeds the
# first arm never touched, because the fixed seed list makes a re-run of the same seeds measure nothing.
cd /c/Users/benpe/ClashBot
PY=./icebow/.venv/Scripts/python.exe
CK=icebow/data/pipeline/s1_icebow_v6lat_s0.pt
until [ -f scratchpad/gauntlet/L67/arm_search.json ]; do sleep 30; done
$PY scratchpad/gauntlet/L67/student_sim.py --ckpt $CK --matches 12 --seed0 911000 --degrade \
    --out scratchpad/gauntlet/L67/arm2_baseline.json > scratchpad/gauntlet/L67/arm2_baseline.out 2>&1
$PY scratchpad/gauntlet/L67/student_search.py --ckpt $CK --matches 12 --seed0 911000 --interval 1 --degrade \
    --mode search --out scratchpad/gauntlet/L67/arm2_search.json > scratchpad/gauntlet/L67/arm2_search.out 2>&1
echo done
