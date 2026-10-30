#!/bin/bash
# launch_arm.sh PORT RUN CPUS PY CONFIG [overrides...] -- lead 10-29: one opponent-calibration arm on a pod's /workspace/oplm copy
# of 33308:/workspace/oplc/cb2 (arm B's tree), with arm B's exact env and fast-loop args (oplc_ftR_l003_a10: init ftR, beta .03,
# lr 3e-5, th_anchor 10, cap 400, save_every 10). Extra overrides after CONFIG are the arm's ONE change (later k=v wins).
# Opt-in env (OPP-PUSH 10-30; unset = unchanged): HOST=ip, TREE=/workspace/mfl/cbm (an origin/main fast-loop tree, mfl_tree.sh),
# JB=jbuild_mfl (facade build dir inside TREE: never compile into a dir linked to cb2), GPU=i.
P=$1; RUN=$2; CPUS=$3; PY=$4; CFG=$5; shift 5
ssh -o BatchMode=yes -i ~/.ssh/runpod_clashbot -p "$P" root@${HOST:-157.157.221.29} "cd ${TREE:-/workspace/oplm/cb2} && mkdir -p /workspace/oplm/logs && \
 export XMX=3g RL_BATCH_SHA=1 ROYALE_ENGINE=crforge CRFORGE_LIB=/workspace/crforge_main/fe364ceb/plain/lib ROYALE_HEROIW_FORM=hero \
 CRFORGE_TABLES=/workspace/oplm/tables/16.635.3 CUDA_VISIBLE_DEVICES=${GPU:-0} PYTHONPATH=${TREE:-/workspace/oplm/cb2}/scratchpad/gauntlet/L74/plan1026/pilot/loop/hook:${TREE:-/workspace/oplm/cb2} \
 CUBLAS_WORKSPACE_CONFIG=:4096:8 CRFORGE_FACADE_BUILD=${TREE:-/workspace/oplm/cb2}/scratchpad/gauntlet/L74/plan1026/pilot/loop/${JB:-jbuild_fe364ceb} \
 OMP_NUM_THREADS=1 CRFORGE_XMX=3g ROYALE_RUNTIME=fin16-linux MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1; \
 $PY -c \"import sys; sys.path.insert(0, 'scratchpad/gauntlet/L74/plan1026/pilot/loop'); import producer, pathlib, os; producer.compile_java(pathlib.Path(os.environ['CRFORGE_FACADE_BUILD']), pathlib.Path(os.environ['CRFORGE_LIB']))\" && \
 setsid nohup timeout 172800 taskset -c $CPUS $PY -u scratchpad/gauntlet/L74/plan1026/pilot/loop/fastloop.py --producers 2 --matches 64 --threads 6 --devices cuda:0 -- \
 --run $RUN --config $CFG actor_device=cpu learner_device=cpu init=/workspace/oplm/opp_ft_s0_R_sim.pt beta0=0.03 beta_min=0.03 beta_max=0.03 \
 lr=3.0e-5 th_anchor=10.0 max_updates=400 save_every=10 learner_device=cuda n_actors=1 $* > /workspace/oplm/logs/$RUN.out 2>&1 < /dev/null & \
 sleep 120; grep -m3 -E 'START|Error|Traceback|refus' /workspace/oplm/logs/$RUN.out | cut -c1-300; tail -n 2 /workspace/oplm/logs/$RUN.out | cut -c1-200"
