#!/bin/bash
# Gate for S11: nohup bash /workspace/s11/s11_gate.sh > /workspace/results/wk/s11_gate.log 2>&1 &
# Waits for the weekend chain's CHAIN_DONE, then runs s11_bait.sh under gpu.lock first, then cpu.lock (the chain's own order).
while [ ! -e /workspace/results/wk/CHAIN_DONE ]; do sleep 60; done
echo "[$(date -u +%T)] CHAIN_DONE seen; taking gpu.lock then cpu.lock"
flock /workspace/gpu.lock flock /workspace/cpu.lock bash /workspace/s11/s11_bait.sh
echo "[$(date -u +%T)] S11 finished rc=$?"
