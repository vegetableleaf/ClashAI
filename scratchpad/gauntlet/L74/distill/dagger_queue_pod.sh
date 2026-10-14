#!/bin/bash
# Pod 12037 queue (10-14 night): after the tau_threatened SIM A/B, distillation iteration 2 (DAgger) on ADAPT, from a fresh
# checkout of current main at /workspace/cb_dag (data linked from /workspace/clashbot). Commands from DISTILL_PLAN.md "Iteration 2".
set -Eeuo pipefail
exec >> /workspace/results/dagger_queue.log 2>&1
until [ -e /workspace/results/TAU_THREAT/DONE ]; do sleep 60; done
cd /workspace/cb_dag
sed -i 's/\r$//' scratchpad/gauntlet/L74/distill/run_distill.sh
export R=/workspace/results/DISTILL_DAGGER R1=/workspace/results/DISTILL_ADAPT \
  TEACHER=icebow/data/bench/rl_royale/wk_adapt_main/wk_adapt_main_latest_grafted.pt \
  STUDENT=icebow/data/bench/rl_royale/wk_adapt_main/wk_adapt_main_latest.pt \
  OUT=icebow/data/bench/rl_royale/distill/distill_adapt_d3.pt
sha256sum $TEACHER $STUDENT $OUT
echo "$(date -u +%T) dagger_smoke"
bash scratchpad/gauntlet/L74/distill/run_distill.sh dagger_smoke && tail -2 $R/run.log
echo "$(date -u +%T) dagger"
bash scratchpad/gauntlet/L74/distill/run_distill.sh dagger
echo "$(date -u +%T) queue done"
