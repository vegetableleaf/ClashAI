#!/bin/bash
# FAST-LIVEOPP: fast-loop smoke of the live-partner config (PLATEAU.md next experiment) in 33903's /workspace/fliv/cb
# (fliv_tree.sh), launch_arm.sh's env and recipe, small: 1 producer x 16 matches, E=4 (16 matches / update), 2 updates.
#   bash fliv_smoke.sh RUN CPUS          (pod; log /workspace/fliv/out/RUN.out)
RUN=$1; CPUS=${2:-178-179}
CB=/workspace/fliv/cb; cd $CB || exit 1
L=scratchpad/gauntlet/L74/plan1026/pilot/loop
export XMX=3g RL_BATCH_SHA=1 ROYALE_ENGINE=crforge CRFORGE_LIB=/workspace/crforge_main/fe364ceb/plain/lib ROYALE_HEROIW_FORM=hero \
 CRFORGE_TABLES=/workspace/oplm/tables/16.635.3 CUDA_VISIBLE_DEVICES=0 PYTHONPATH=$CB/$L/hook:$CB \
 CUBLAS_WORKSPACE_CONFIG=:4096:8 CRFORGE_FACADE_BUILD=$CB/$L/jbuild_fe364ceb OMP_NUM_THREADS=1 CRFORGE_XMX=3g \
 ROYALE_RUNTIME=fin16-linux MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
PY=/workspace/venvf16/bin/python
exec timeout 7200 taskset -c $CPUS $PY -u $L/fastloop.py --producers 1 --matches 16 --threads 2 --devices cuda:0 -- \
 --run $RUN --config scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_calib_live.yaml actor_device=cpu \
 init=/workspace/oplm/opp_ft_s0_R_sim.pt beta0=0.003 beta_min=0.003 beta_max=0.003 lr=3.0e-5 th_anchor=10.0 \
 save_every=10 learner_device=cuda n_actors=1 E=4 max_updates=2 --smoke > /workspace/fliv/out/$RUN.out 2>&1 < /dev/null
