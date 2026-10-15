#!/bin/bash
# Raw state-potential rows for fitting A3' (tower exchange rate; HANDOFF 10-15 ~03:30): after WAIT_DIR/DONE, a fresh checkout
# (/workspace/cb_s6 from /workspace/in/repo_s6.tgz, data linked from /workspace/clashbot), then preflight_a1a2.py audit
# --policies il --dump-rows with r1 (live lineage) -> /workspace/results/ROWS_R1/rows.jsonl, ROWS_R1/DONE.
#   rows_pod.sh WAIT_DIR [MATCHES]
set -Eeuo pipefail
W=$1; M=${2:-1000}; R=/workspace/results; C=/workspace/cb_s6
mkdir -p $R; exec >> $R/rows_pod.log 2>&1
echo "$(date -u +%T) queued after $W"
until [ -e $W/DONE ]; do sleep 60; done
if [ ! -d $C/pipeline ]; then
  mkdir -p $C && tar xzf /workspace/in/repo_s6.tgz --no-same-owner -C $C
  mkdir -p $C/icebow && ln -sfn /workspace/clashbot/icebow/data $C/icebow/data && ln -sfn /workspace/clashbot/research $C/research
fi
cd $C
export PYTHONPATH=$C ROYALE_RUNTIME=20261012-linux OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
echo "$(date -u +%T) start ($M matches, $(nproc) cores)"
flock /workspace/cpu.lock /workspace/venv33/bin/python scratchpad/gauntlet/L74/reward/preflight_a1a2.py audit --out $R/ROWS_R1 \
  --ckpt icebow/data/bench/rl_royale/newsim_r1/newsim_base_r1_final_grafted.pt --matches $M --workers ${WORKERS:-25} \
  --policies il --dump-rows > $R/ROWS_R1.log 2>&1 || echo "ROWS EXIT $?"
touch $R/ROWS_R1/DONE
echo "$(date -u +%T) done"
