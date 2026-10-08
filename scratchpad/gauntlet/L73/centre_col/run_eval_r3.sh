#!/bin/bash
# offline before/after for R3 v2, then the centre-column slices for base / v1 / v2 (one GPU job at a time)
cd "$(dirname "$0")"
R=/c/Users/benpe/ClashBot/icebow/data/bench/rl_royale/rseries_r3
PY=/c/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe
$PY offline_eval.py offline_r3_v2.json $R/rseries_r3_u0050.pt $R/rseries_r3_u0050_cellref5.pt > offline_r3_v2.out 2> offline_r3_v2.err
$PY slices.py slices_r3.json $R/rseries_r3_u0050.pt $R/rseries_r3_u0050_cellref.pt $R/rseries_r3_u0050_cellref5.pt > slices_r3.out 2> slices_r3.err
echo EVAL_DONE
