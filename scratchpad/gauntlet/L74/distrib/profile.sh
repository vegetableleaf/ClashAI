#!/usr/bin/env bash
# W16 learner profile ON the learner pod, alongside run_learner.sh NAME started with RL_PROFILE=1 (phase timings in the
# log): GPU utilisation every 250 ms until the learner exits (py-spy cannot attach on these pods: no ptrace).
#   bash profile.sh NAME   -> /workspace/w16/prof_NAME/gpu.csv
set -uo pipefail
NAME=$1; D=/workspace/w16/prof_$NAME; mkdir -p $D
PJ=/workspace/cb_w16/scratchpad/gauntlet/L68/rl/w16_$NAME/pid.json
until [ -s $PJ ]; do sleep 2; done
PID=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['learner'])" $PJ)
nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used --format=csv,noheader -lms 250 > $D/gpu.csv &
G=$!
while kill -0 $PID 2>/dev/null; do sleep 5; done
kill $G
echo "PROFILE_DONE $D"
