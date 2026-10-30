#!/bin/bash
# GROW-SMOKE (33903): real rl_royale --smoke, pilot.yaml minus fastloop (/workspace/grow/pilot_smoke.yaml):
#   run_rl.sh RUN CPUS INIT [k=v ...]     log /workspace/grow/out/RUN.log
R=$1; C=$2; I=$3; shift 3
CB=/workspace/grow/cb; cd $CB || exit 1
export PYTHONPATH=$CB ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 ROYALE_ENGINE=crforge CRFORGE_LIB=/workspace/crforge_main/5e8089a4/plain/lib \
 CRFORGE_TABLES=/workspace/opplearn/tables/16.635.3 CRFORGE_FACADE_BUILD=/workspace/grow/jbuild CUBLAS_WORKSPACE_CONFIG=:4096:8 \
 CRFORGE_BARREL_DECOY_SIM=1 ROYALE_HEROIW_PRESS=live CUDA_VISIBLE_DEVICES=0 RL_BATCH_SHA=1
exec timeout 10800 taskset -c $C /workspace/venvf16/bin/python -u -m pipeline.rl_royale --config /workspace/grow/pilot_smoke.yaml \
 --run $R --smoke init=$I "$@" > /workspace/grow/out/$R.log 2>&1 < /dev/null
