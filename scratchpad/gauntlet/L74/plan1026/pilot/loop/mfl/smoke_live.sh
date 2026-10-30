#!/bin/bash
# FASTLOOP-FIX: the fast loop on opp_learner_calib_live.yaml (the live CLXIII partner) in a mfl tree on 33903, with the arm's
# recipe (launch_arm.sh / oplc_ftR_l0003_live: init ftR, beta .003, lr 3e-5, th_anchor 10). Log /workspace/mfl/out/RUN.out.
#   bash smoke_live.sh RUN CPUS          FL="fastloop args" (default 1 producer x 16 cpu)  RL="rl k=v" (default E=4 2 updates --smoke)
RUN=$1; CPUS=$2
CB=${CB:-/workspace/mfl/cbg}; cd $CB || exit 1
L=scratchpad/gauntlet/L74/plan1026/pilot/loop
export XMX=3g RL_BATCH_SHA=1 ROYALE_ENGINE=crforge CRFORGE_LIB=/workspace/crforge_main/fe364ceb/plain/lib ROYALE_HEROIW_FORM=hero \
 CRFORGE_TABLES=/workspace/oplm/tables/16.635.3 CUDA_VISIBLE_DEVICES=${GPU-} PYTHONPATH=$CB/$L/hook:$CB \
 CUBLAS_WORKSPACE_CONFIG=:4096:8 CRFORGE_FACADE_BUILD=$CB/$L/jbuild_mfl OMP_NUM_THREADS=1 CRFORGE_XMX=3g \
 ROYALE_RUNTIME=fin16-linux MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
PY=/workspace/venvf16/bin/python
exec timeout ${TMO:-7200} taskset -c $CPUS $PY -u $L/fastloop.py ${FL:---producers 1 --matches 16 --threads 2 --devices cpu} -- \
 --run $RUN --config scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_calib_live.yaml actor_device=cpu \
 init=/workspace/oplm/opp_ft_s0_R_sim.pt beta0=0.003 beta_min=0.003 beta_max=0.003 lr=3.0e-5 th_anchor=10.0 \
 save_every=10 learner_device=${LD:-cpu} n_actors=1 ${RL:-E=4 max_updates=2 --smoke} > /workspace/mfl/out/$RUN.out 2>&1 < /dev/null
