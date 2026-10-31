#!/bin/bash
# switch_arm4.sh MODE -- OPP-PUSH arm 4 on 33903 (pod side; tree /workspace/mfl/cbopp; launch_arm.sh's env).
#   smoke : CPU-only smoke of opp_learner_calib_live_d3env.yaml (E 4, 1 update, CPUs 0-15, no GPU: the live arm owns it)
#   switch: wait for oplc_ftR_l0003_live_u0120.pt, stop that run (fastloop PID $OLD + its children, captured first), then
#           launch arm 4 = oplc_ftR_l0003_d3env (seed 0, the live recipe + D3 conditions) on its CPUs 240-255,180-185 + GPU.
# Log /workspace/oplm/logs/switch_arm4.out.
MODE=$1; OLD=${OLD:-1602464}
cd /workspace/mfl/cbopp || exit 1
L=scratchpad/gauntlet/L74/plan1026/pilot/loop
CFG=scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_calib_live_d3env.yaml
export XMX=3g RL_BATCH_SHA=1 ROYALE_ENGINE=crforge CRFORGE_LIB=/workspace/crforge_main/fe364ceb/plain/lib ROYALE_HEROIW_FORM=hero \
 CRFORGE_TABLES=/workspace/oplm/tables/16.635.3 PYTHONPATH=$PWD/$L/hook:$PWD CUBLAS_WORKSPACE_CONFIG=:4096:8 \
 CRFORGE_FACADE_BUILD=$PWD/$L/jbuild_mfl OMP_NUM_THREADS=1 CRFORGE_XMX=3g ROYALE_RUNTIME=fin16-linux MKL_NUM_THREADS=1 \
 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
PY=/workspace/venvf16/bin/python
RL="actor_device=cpu init=/workspace/oplm/opp_ft_s0_R_sim.pt beta0=0.003 beta_min=0.003 beta_max=0.003 lr=3.0e-5 th_anchor=10.0 save_every=10 n_actors=1"
if [ "$MODE" = smoke ]; then
  CUDA_VISIBLE_DEVICES= timeout 1800 taskset -c 0-15 $PY -u $L/fastloop.py --producers 1 --matches 16 --threads 4 --devices cpu -- \
    --run d3env_smoke1 --config $CFG $RL learner_device=cpu max_updates=400 E=4 max_updates=1 --smoke > /workspace/oplm/logs/d3env_smoke1.out 2>&1
  grep -E 'LEAGUE|SMOKE PASS|Traceback|Error' /workspace/oplm/logs/d3env_smoke1.out | cut -c1-200; exit
fi
CK=/workspace/mfl/cbopp/icebow/data/bench/rl_royale/oplc_ftR_l0003_live/oplc_ftR_l0003_live_u0120.pt
until [ -f $CK ]; do sleep 60; done; sleep 30
KIDS=$(pgrep -P $OLD | tr '\n' ' ')
echo "$(date -u +%FT%TZ) u0120 present; stopping $OLD (children: $KIDS)"
kill $OLD; sleep 20; [ -n "$KIDS" ] && kill $KIDS 2>/dev/null; sleep 5
ps -p $OLD $KIDS -o pid= 2>/dev/null | wc -l
CUDA_VISIBLE_DEVICES=0 setsid nohup timeout 172800 taskset -c 240-255,180-185 $PY -u $L/fastloop.py --producers 2 --matches 64 --threads 6 \
  --devices cuda:0 -- --run oplc_ftR_l0003_d3env --config $CFG $RL learner_device=cuda max_updates=400 \
  > /workspace/oplm/logs/oplc_ftR_l0003_d3env.out 2>&1 < /dev/null &
sleep 120; echo "$(date -u +%FT%TZ) arm 4 launched"; grep -m3 -E 'START|LEAGUE|Traceback|Error' /workspace/oplm/logs/oplc_ftR_l0003_d3env.out | cut -c1-200
