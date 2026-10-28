# LOOP-LRN pod environment (33920): source it, then run python from /workspace/lrn/cb
export CB=/workspace/lrn/cb PY=/workspace/venvf16/bin/python
export PYTHONPATH=$CB:/workspace/lrn/d2/stage/pylib ROYALE_RUNTIME=fin16-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 ROYALE_ENGINE=crforge CRFORGE_LIB=/workspace/lrn/d2/stage/lib \
  CRFORGE_TABLES=/workspace/crforge_cache/tables/16.402.22 CRFORGE_FACADE_BUILD=/workspace/lrn/buildH
