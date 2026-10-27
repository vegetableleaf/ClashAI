#!/bin/bash
# S4 add-on (lead, hardware choice): fp32 / TF32 / bf16 plateau rows/s + FLOPs per row + decision-change rate, after s4_chain.sh.
until [ -f /workspace/speed/s4/S4_DONE ]; do sleep 10; done
cd /workspace/cb; export PYTHONPATH=/workspace/cb
/workspace/venvf15/bin/python scratchpad/gauntlet/L74/speed/s4_bench.py --part precision --out /workspace/speed/s4/precision.json > /workspace/speed/s4/precision.log 2>&1
touch /workspace/speed/s4/S4_PREC_DONE
