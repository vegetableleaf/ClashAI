# LEARNER-SPEED bench env on 31892 (source it; python from /workspace/lspeed/cb). CPUs 0-5; take /workspace/BENCH_LOCK first.
W=/workspace/loop
export CB=/workspace/lspeed/cb PY=$W/venv/bin/python CPUS=0-5
export ROYALE_RUNTIME=fin16-linux ROYALE_ENGINE=crforge ROYALE_HEROIW_FORM=hero CRFORGE_LIB=$W/crforge/lib \
  CRFORGE_TABLES=$W/crforge/tables/16.635.3 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONNOUSERSITE=1 PYTHONPATH=$CB:$W/pylib CUBLAS_WORKSPACE_CONFIG=:4096:8 CRFORGE_FACADE_BUILD=$W/jbuild \
  JAVA_TOOL_OPTIONS="--add-modules=jdk.incubator.foreign --enable-native-access=ALL-UNNAMED" \
  NPY_DISABLE_CPU_FEATURES=X86_V4,AVX512_ICL OPENBLAS_CORETYPE=ZEN CRFORGE_BARREL_DECOY_SIM=1 ROYALE_HEROIW_PRESS=live
