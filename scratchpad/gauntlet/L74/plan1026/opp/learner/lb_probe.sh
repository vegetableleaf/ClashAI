#!/bin/bash
# lb_probe.sh CPUS LR [LR ...] -- OPP-PUSH arm 3 equal-KL lr probe (pod side, fast-loop tree /workspace/mfl/cbm, launch_arm.sh's env):
# per LR a fresh 2-update run of opp_learner_calib_live_lb.yaml (init ftR, seed 1, the arm's recipe), then prints update 0's KL:
# 'step1' = u0's summary KL card + cell (measured before the 2nd full-batch step = KL after step 1, vs the init = the u0 policy)
# and 'update' = u1's first-minibatch KL to the init (= the whole update 0: the policy before u0 was the init). Target: update
# ~0.02, step1 <= 0.03 (lead 10-31). Base recipe for scale: update-0 KL 0.0094 (s1f). Log /workspace/oplm/logs/lbprobe.out.
CPUS=$1; shift
cd /workspace/mfl/cbm || exit 1
L=scratchpad/gauntlet/L74/plan1026/pilot/loop
export XMX=3g RL_BATCH_SHA=1 ROYALE_ENGINE=crforge CRFORGE_LIB=/workspace/crforge_main/fe364ceb/plain/lib ROYALE_HEROIW_FORM=hero \
 CRFORGE_TABLES=/workspace/oplm/tables/16.635.3 CUDA_VISIBLE_DEVICES=0 PYTHONPATH=$PWD/$L/hook:$PWD CUBLAS_WORKSPACE_CONFIG=:4096:8 \
 CRFORGE_FACADE_BUILD=$PWD/$L/jbuild_mfl OMP_NUM_THREADS=1 CRFORGE_XMX=3g ROYALE_RUNTIME=fin16-linux MKL_NUM_THREADS=1 \
 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
PY=/workspace/venvf16/bin/python
for LR in "$@"; do
  RUN=lbprobe_$LR
  timeout 1800 taskset -c $CPUS $PY -u $L/fastloop.py --producers 2 --matches 64 --threads 6 --devices cuda:0 -- \
    --run $RUN --config scratchpad/gauntlet/L74/plan1026/opp/learner/opp_learner_calib_live_lb.yaml actor_device=cpu \
    init=/workspace/oplm/opp_ft_s0_R_sim.pt beta0=0.003 beta_min=0.003 beta_max=0.003 lr=$LR th_anchor=10.0 save_every=10 \
    learner_device=cuda n_actors=1 seed=1 max_updates=2 > /workspace/oplm/logs/$RUN.out 2>&1 < /dev/null
  $PY -c "
import json, sys
L = [json.loads(l) for l in open('scratchpad/gauntlet/L68/rl/$RUN/train_log.jsonl') if '\"first_minibatch\"' in l]
u0, u1 = L[0], L[1]; f = u1['first_minibatch']
print('LR $LR step1 %.4f update %.4f | u0 clip %s gnorm %s rows %s' % ((u0['kl_card'] or 0) + (u0['kl_cell'] or 0),
      f['kl_card'] + f['kl_cell'], u0.get('clip_frac'), u0.get('grad_norm_mean'), u0.get('rows')))
" 2>&1 | tail -1
done
echo LBPROBE DONE
