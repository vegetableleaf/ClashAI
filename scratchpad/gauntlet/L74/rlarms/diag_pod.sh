#!/bin/bash
# Critic diagnostic on a pod (F2 acceptance check, 10-15): after WAIT_DIR/DONE, critic_diag.py on the F1 run (rlarm_gae) at u250
# (its league snapshots u195-u250 are on disk: the exact training mix) and at u65 (--allow-missing: its old snapshots were
# evicted, so the mix is init + externals + surviving snapshots -- stated in the output). -> /workspace/results/CRITIC_DIAG/.
#   diag_pod.sh WAIT_DIR [MATCHES]      (CB=/workspace/clashbot; critic_diag.py shipped to /workspace/in/)
set -Eeuo pipefail
W=$1; M=${2:-1000}; CB=${CB:-/workspace/clashbot}; PY=/workspace/venv33/bin/python; O=/workspace/results/CRITIC_DIAG
RL=icebow/data/bench/rl_royale/rlarm_gae; CFG=/workspace/results/rlarm_gae/rlarm_gae.yaml
mkdir -p $O; exec >> $O/run.log 2>&1
echo "$(date -u +%T) queued after $W"
until [ -e $W/DONE ]; do sleep 60; done
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=20261012-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
for U in 0250 0065; do
  X=(); [ $U = 0065 ] && X=(--allow-missing)
  echo "$(date -u +%T) u$U"
  flock /workspace/cpu.lock $PY /workspace/in/critic_diag.py --ckpt $RL/rlarm_gae_u$U.pt --config $CFG --out $O/u$U \
    --matches $M --workers ${WORKERS:-25} --seed-start 745000 "${X[@]}" > $O/u$U.log 2>&1 || echo "DIAG EXIT $? u$U"
done
touch $O/DONE
echo "$(date -u +%T) done"
