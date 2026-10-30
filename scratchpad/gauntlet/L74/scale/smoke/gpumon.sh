#!/bin/bash
# GROW-SMOKE: per-PID GPU memory every 10 s -> /workspace/grow/out/gpumon.txt (stop: kill this PID)
while true; do echo "$(date +%T) $(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader | tr '\n' ';')" >> /workspace/grow/out/gpumon.txt; sleep 10; done
