# V1-LIVEROWS pod env (33553): source this. Code copy = /workspace/v1live/cb (git archive of CODE_HEAD + live_rows/ + the
# laptop's live_card_catalog.json); pyarrow in a private target dir; icebow/data -> /workspace/loop/cb/icebow/data.
export V1=/workspace/v1live CB=/workspace/v1live/cb PY=/workspace/venv/bin/python
export PYTHONPATH=$CB:/workspace/v1live/pylib OPP_VOCAB=$CB/scratchpad/gauntlet/L74/plan1026/opp/vocab_hf.json \
  RD_DIR=$CB/scratchpad/gauntlet/L74/plan1026/redrive OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
LR=$CB/scratchpad/gauntlet/L74/plan1026/opp/live_rows
