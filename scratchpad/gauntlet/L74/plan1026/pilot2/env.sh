# PILOT2 pod env (source it; pod booted by loop_pod.sh up, ENTRY=-c). = pod_boot.sh's loop env + the AVX-512 numpy / BLAS
# paths (EPYC 9554) + the speed-stack env (FASTLOOP_CELLS1 / FASTLOOP_SHARDS, ROLLOUT-SPEED).
W=/workspace/loop
export CB=$W/cb PY=$W/venv/bin/python L=scratchpad/gauntlet/L74/plan1026/pilot/loop P2=scratchpad/gauntlet/L74/plan1026/pilot2
export ROYALE_RUNTIME=fin16-linux ROYALE_ENGINE=crforge ROYALE_HEROIW_FORM=hero CRFORGE_LIB=$W/crforge/lib \
  CRFORGE_TABLES=$W/crforge/tables/16.635.3 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 PYTHONPATH=$CB:$W/pylib RL_BATCH_SHA=1 CUBLAS_WORKSPACE_CONFIG=:4096:8 CRFORGE_FACADE_BUILD=$W/jbuild \
  JAVA_TOOL_OPTIONS="--add-modules=jdk.incubator.foreign --enable-native-access=ALL-UNNAMED" \
  NPY_DISABLE_CPU_FEATURES=X86_V4,AVX512_ICL OPENBLAS_CORETYPE=ZEN FASTLOOP_CELLS1=1 FASTLOOP_SHARDS=3
unset ROYALE_HEROIW_PRESS   # pilot2.yaml heroiw_press: live sets it (rl_royale refuses a different env value)
