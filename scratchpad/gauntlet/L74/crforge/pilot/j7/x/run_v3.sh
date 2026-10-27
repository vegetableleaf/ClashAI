#!/bin/bash
# pod 33920 /workspace/pilot/j7: fin arms with the deck-map fix (fin_run.py), on the 138 (runs_v3) then the 811 (runs_x)
cd /workspace/pilot/j7
rm -rf runs_v3 runs_x/fin1*
mkdir -p runs_v3
PL=plans R=runs_v3 ./run_fin.sh
PL=plans_x R=runs_x ./run_fin.sh
echo $(date -u +%T) done > run_v3.done
