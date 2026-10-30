#!/bin/bash
# launch_arm_prod.sh PORT RUN CPUS NACT CONFIG [overrides...] -- OPP-LIVEPARTNER 10-30: launch_arm.sh's arm (same tree
# /workspace/oplm/cb2, same env, same recipe overrides: ftR init, beta .03 default, lr 3e-5, th_anchor 10, cap 400, save_every 10,
# CUDA learner) on PRODUCTION rl_royale (CPU actors) instead of the fast loop. Why: the fast loop refuses a policy 'live' opponent
# (producer.py:702), and its decide path has no engine BoardState for the LIVE_OPTIONS rules (decision_options.match_kwargs reads
# m._cur[1] towers / units, m.state crown_towers), so the CLXIII live-stack partner (opp_learner_calib_live.yaml) runs here.
# Env differences vs launch_arm.sh: CRFORGE_XMX 1g + serial GC, 1 CPU per JVM (run_calib.sh's production setting: NACT JVMs).
# Log: /workspace/oplm/logs/RUN.out. Resume after a stop: the same command + --resume. Stop: kill the rl_royale PID (exact PID).
# Opt-in env (OPP-PUSH 10-30; unset = the command above, unchanged): GPU=i (CUDA_VISIBLE_DEVICES, default 0, for a 2-GPU pod);
# ALLOC=expandable_segments:True (PYTORCH_CUDA_ALLOC_CONF: the allocator only, numerics unchanged; lets two 8.5 GB-peak learners
# that each RESERVE ~13 GB share one 24 GB card -- (b) untested). HOST=ip (pods off 157.157.221.29).
P=$1; RUN=$2; CPUS=$3; NACT=$4; CFG=$5; shift 5
ssh -o BatchMode=yes -i ~/.ssh/runpod_clashbot -p "$P" root@${HOST:-157.157.221.29} "cd /workspace/oplm/cb2 && mkdir -p /workspace/oplm/logs && \
 export RL_BATCH_SHA=1 ROYALE_ENGINE=crforge CRFORGE_LIB=/workspace/crforge_main/fe364ceb/plain/lib ROYALE_HEROIW_FORM=hero \
 CRFORGE_TABLES=/workspace/oplm/tables/16.635.3 CUDA_VISIBLE_DEVICES=${GPU:-0} ${ALLOC:+PYTORCH_CUDA_ALLOC_CONF=$ALLOC }PYTHONPATH=/workspace/oplm/cb2/scratchpad/gauntlet/L74/plan1026/pilot/loop/hook:/workspace/oplm/cb2 \
 CUBLAS_WORKSPACE_CONFIG=:4096:8 CRFORGE_FACADE_BUILD=/workspace/oplm/cb2/scratchpad/gauntlet/L74/plan1026/pilot/loop/jbuild_fe364ceb \
 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CRFORGE_XMX=1g ROYALE_RUNTIME=fin16-linux MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
 JAVA_TOOL_OPTIONS='-XX:+UseSerialGC -XX:ActiveProcessorCount=1'; \
 setsid nohup timeout 604800 taskset -c $CPUS /workspace/venvf16/bin/python -u -m pipeline.rl_royale \
 --run $RUN --config $CFG actor_device=cpu init=/workspace/oplm/opp_ft_s0_R_sim.pt beta0=0.03 beta_min=0.03 beta_max=0.03 \
 lr=3.0e-5 th_anchor=10.0 max_updates=400 save_every=10 learner_device=cuda n_actors=$NACT $* > /workspace/oplm/logs/$RUN.out 2>&1 < /dev/null & \
 sleep 180; grep -m3 -E 'START|Error|Traceback|refus' /workspace/oplm/logs/$RUN.out | cut -c1-300; tail -n 2 /workspace/oplm/logs/$RUN.out | cut -c1-200"
