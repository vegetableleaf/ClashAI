#!/usr/bin/env bash
# W16 learner profile ON the learner pod, alongside a running run_learner.sh NAME: GPU utilisation every 250 ms +
# py-spy (collapsed stacks, --idle, 20 Hz) of the learner process until it exits.   bash profile.sh NAME
set -uo pipefail
NAME=$1; D=/workspace/w16/prof_$NAME; mkdir -p $D
PJ=/workspace/cb_w16/scratchpad/gauntlet/L68/rl/w16_$NAME/pid.json
until [ -s $PJ ]; do sleep 2; done
PID=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['learner'])" $PJ)
nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used --format=csv,noheader -lms 250 > $D/gpu.csv &
G=$!
/workspace/w16/pyspy/bin/py-spy record -p $PID --idle -r 20 -f raw -o $D/learner.txt > $D/pyspy.log 2>&1
kill $G
echo "PROFILE_DONE $D"
