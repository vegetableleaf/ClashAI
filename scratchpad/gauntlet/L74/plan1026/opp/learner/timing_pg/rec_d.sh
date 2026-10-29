#!/bin/bash
# OPP-LEARN-D variance check input: one 64-match ftR rollout with timing_pg (FASTLOOP_RECORDS = every slot row + lp_th), CPU.
# Stop by exact PID once rec_d/records_u0000.pkl exists (the CPU update is not needed).
set -f
cd /workspace/oplc
FASTLOOP_RECORDS=/workspace/oplc/rec_d CB=/workspace/oplc/cbd TABLES=/workspace/crforge_cache/tables/16.635.3 LOGS=/workspace/oplc/logsd XMX=2g \
  FAST_ARGS="--producers 2 --matches 32 --threads 4 --devices cpu" bash /workspace/oplc/fl_pod.sh fast oplcd_rec 170-185 \
  scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_calib.yaml init=/workspace/oplc/opp_ft_s0_R_sim.pt E=16 beta0=0.03 beta_min=0.03 \
  beta_max=0.03 lr=3.0e-5 th_anchor=10.0 freeze_heads=[ability] timing_pg=32 max_updates=1 save_every=10 n_actors=1
