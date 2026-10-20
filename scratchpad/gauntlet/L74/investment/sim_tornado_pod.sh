#!/bin/bash
# W5 / I2: run the two Tornado SIM checks on FIN13 (the training SIM) on a pod. NOT RUN by W5: until ~06:00 EDT 10-20 the pods
# run the L16 successor seeds, and after that the lead decides (WORKER_RULES). Both checks already ran on the laptop on
# upstream royalesim 0.1.35 (sim_tornado_v35.*, sim_replay_v35.*); this repeats them on fin13 for the training SIM's answer.
#   laptop:  POD=13396 bash scratchpad/gauntlet/L74/investment/sim_tornado_pod.sh
# Ships 3 files to /workspace/w5, runs each check as ONE process under /workspace/cpu.lock (~1-3 min each on the laptop's
# 0.1.35), pulls the JSON + summaries back next to this script. Never stops the pod.
set -euo pipefail
case "${POD:?POD=13396|14009|15617|19899}" in
  13396) H=root@64.247.206.76 ;; 14009) H=root@64.247.206.76 ;; 19899) H=root@64.247.206.76 ;; 15617) H=root@216.81.151.5 ;;
  *) echo "unknown POD $POD"; exit 2 ;;
esac
K=~/.ssh/runpod_clashbot; L=scratchpad/gauntlet/L74/investment
SSH=(ssh -i "$K" -p "$POD" "$H"); SCP=(scp -i "$K" -P "$POD")
"${SSH[@]}" 'mkdir -p /workspace/w5'
"${SCP[@]}" "$L/sim_tornado.py" "$L/sim_replay.py" "$L/sim_replay_cases.json" "$H:/workspace/w5/"
"${SSH[@]}" 'cd /workspace/w5 && export CB_REPO=/workspace/cb_stepd PYTHONPATH=/workspace/cb_stepd ROYALE_RUNTIME=fin13-linux \
  OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 && \
  flock /workspace/cpu.lock /workspace/venvf13/bin/python sim_tornado.py --activate --out sim_tornado_fin13.json \
    > sim_tornado_fin13.out 2>&1 && \
  flock /workspace/cpu.lock /workspace/venvf13/bin/python sim_replay.py --activate --cases sim_replay_cases.json \
    --out sim_replay_fin13.json > sim_replay_fin13.out 2>&1; echo exit $?'
for f in sim_tornado_fin13.json sim_tornado_fin13.out sim_replay_fin13.json sim_replay_fin13.out; do
  "${SCP[@]}" "$H:/workspace/w5/$f" "$L/$f"
done
python "$L/sim_tornado_table.py" "$L/sim_tornado_fin13.json" > "$L/sim_tornado_fin13.table"
tail -3 "$L/sim_replay_fin13.out"
