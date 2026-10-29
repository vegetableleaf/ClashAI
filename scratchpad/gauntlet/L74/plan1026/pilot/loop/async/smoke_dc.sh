#!/bin/bash
# LOOP-ASYNC trainer pre-ship smoke (33308, CPU learner + actors): rl_royale --smoke with ppo_decoupled absent, then on.
CB=/workspace/async/cb; cd $CB || exit 1
export PYTHONPATH=$CB:/workspace/d2/stage/pylib ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 ROYALE_ENGINE=crforge CUDA_VISIBLE_DEVICES= \
  CRFORGE_LIB=/workspace/crforge_main/fe364ceb/plain/lib CRFORGE_TABLES=/workspace/crforge_cache/tables/16.635.3 CRFORGE_FACADE_BUILD=$CB/scratchpad/gauntlet/L74/plan1026/pilot/loop/jbuild_fe364ceb
CFG=scratchpad/gauntlet/L74/stepd/cfg/succ48_x_s101.yaml
T=$(date +%s)
for arm in off on; do
  X=; [ $arm = on ] && X="kl_ref_refresh_every=1 ppo_decoupled=2.0"
  taskset -c 216-231 /workspace/venvf16/bin/python -u -m pipeline.rl_royale --run async_smk_${arm}_$T --config $CFG --smoke \
    actor_device=cpu learner_device=cpu $X > /workspace/async/smk_$arm.log 2>&1
  echo "$arm rc $?"; grep -E "SMOKE|config sha" /workspace/async/smk_$arm.log | cut -c1-200
done
echo SMOKES DONE
