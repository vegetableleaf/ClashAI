# ROLLOUT-SPEED env on 31892 (source it). Tree /workspace/rs/cb = hard-link copy of /workspace/loop/cb (92bd817) + HEAD loop files.
W=/workspace/loop
export CB=/workspace/rs/cb PY=$W/venv/bin/python L=scratchpad/gauntlet/L74/plan1026/pilot/loop
export ROYALE_RUNTIME=fin16-linux ROYALE_ENGINE=crforge ROYALE_HEROIW_FORM=hero CRFORGE_LIB=$W/crforge/lib \
  CRFORGE_TABLES=$W/crforge/tables/16.635.3 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 PYTHONPATH=$CB:$W/pylib CUBLAS_WORKSPACE_CONFIG=:4096:8 CRFORGE_FACADE_BUILD=/workspace/rs/jbuild \
  JAVA_TOOL_OPTIONS="--add-modules=jdk.incubator.foreign --enable-native-access=ALL-UNNAMED" \
  NPY_DISABLE_CPU_FEATURES=X86_V4,AVX512_ICL OPENBLAS_CORETYPE=ZEN CRFORGE_BARREL_DECOY_SIM=1 ROYALE_HEROIW_PRESS=live
lock() { echo "ROLLOUT-SPEED $(date -u +%FT%TZ) $*" > /workspace/BENCH_LOCK; }
unlock() { grep -q '^ROLLOUT-SPEED' /workspace/BENCH_LOCK 2>/dev/null && rm -f /workspace/BENCH_LOCK; }
