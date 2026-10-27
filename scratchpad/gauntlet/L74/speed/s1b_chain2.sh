#!/bin/bash
# S1b steps 3 (merge) and 4 (bf16 on top), after s1b_chain.sh (steps 1-2) finished.
until [ -f /workspace/speed/S1B_DONE ]; do sleep 10; done
S=/workspace/cb/scratchpad/gauntlet/L74/speed
STEPS="refine,cue,merge" bash $S/s1b_chain.sh
STEPS="refine,cue,merge" EXTRA="--amp bf16" TAG="_bf16" bash $S/s1b_chain.sh
