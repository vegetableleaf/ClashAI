#!/bin/bash
# S1b: identity (E8 x G4 vs ref_e8g4) + N=2048 throughput per fast-path step, on pod 30408.
#   STEPS="refine refine,cue" TAG= EXTRA= W=48 COH=2 bash s1b_chain.sh
cd /workspace/cb; export ROYALE_RUNTIME=fin15-linux PYTHONPATH=/workspace/cb
INTERP=/workspace/venvf15/bin/python; H=scratchpad/gauntlet/L74/speed/harness.py
C=scratchpad/gauntlet/L74/stepd/cfg/succ48_x_s101.yaml; O=/workspace/speed
for F in ${STEPS:-refine refine,cue}; do
  T=$(echo $F | tr , _)
  "$INTERP" $H --cfg $C --E 8 --G 4 --mode batched --workers 4 --cohorts 2 --device cuda --fast $F $EXTRA --out $O/id_e8g4_$T$TAG > $O/id_e8g4_$T$TAG.log 2>&1
  "$INTERP" scratchpad/gauntlet/L74/speed/compare.py $O/ref_e8g4/results.jsonl $O/id_e8g4_$T$TAG/results.jsonl > $O/id_e8g4_$T$TAG/compare.json
  "$INTERP" $H --cfg $C --E 512 --G 4 --mode batched --workers ${W:-48} --cohorts ${COH:-2} --device cuda --fast $F $EXTRA --out $O/b_n2048_$T$TAG > $O/b_n2048_$T$TAG.log 2>&1
done
touch $O/S1B_DONE$TAG
