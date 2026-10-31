# PILOT2 Lc env on pod 33308 (L-RESUME 10-31; source it, arm.sh P2ENV=...): env.sh's loop env on /workspace/loopL (built by
# setup_Lc.sh = the PRO pods' /workspace/loop layout) with 33308's venvf16 (torch 2.11.0+cu128 = pod_boot's requirements,
# royalegym 0.1.23 / royalesim 0.1.36 = engine16), GPU 0 only (GPU 1 stays free), ONE server (FASTLOOP_SHARDS 1: eager mode
# has no graph pools to split). 33308 (EPYC 7702, Zen2) is the byte-exact reference host: no AVX-512 overrides.
W=/workspace/loopL
export CB=$W/cb PY=/workspace/venvf16/bin/python L=scratchpad/gauntlet/L74/plan1026/pilot/loop P2=scratchpad/gauntlet/L74/plan1026/pilot2
export ROYALE_RUNTIME=fin16-linux ROYALE_ENGINE=crforge ROYALE_HEROIW_FORM=hero CRFORGE_LIB=$W/crforge/lib \
  CRFORGE_TABLES=$W/crforge/tables/16.635.3 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 PYTHONPATH=$CB:$W/pylib RL_BATCH_SHA=1 CUBLAS_WORKSPACE_CONFIG=:4096:8 CRFORGE_FACADE_BUILD=$W/jbuild \
  JAVA_TOOL_OPTIONS="--add-modules=jdk.incubator.foreign --enable-native-access=ALL-UNNAMED" \
  FASTLOOP_CELLS1=1 FASTLOOP_SHARDS=1 CUDA_VISIBLE_DEVICES=0
unset ROYALE_HEROIW_PRESS NPY_DISABLE_CPU_FEATURES OPENBLAS_CORETYPE
