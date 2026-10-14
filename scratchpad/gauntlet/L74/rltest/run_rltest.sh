#!/bin/bash
# RL T_gate test (owner 2026-10-13, one change): r1's exact config continued 20 updates from its final pre-graft
# checkpoint (newsim_base_main_u0060), control T_gate null (= T .5) vs treatment T_gate .1. Then each final checkpoint is
# scored greedy (gap.py D1) and as the RL sampler (D0) on the GAP_r1 paired games; the control pod also scores the init.
#   setup:  bash run_rltest.sh setup            (code + data from /workspace/in, CUDA torch, runtime check)
#   run:    bash run_rltest.sh run rltest_ctrl [init]   |   bash run_rltest.sh run rltest_tg01
set -Eeuo pipefail
CB=/workspace/cb_rl; IN=/workspace/in; PY=/workspace/venv33/bin/python
if [ "$1" = setup ]; then
  exec >> /workspace/rl_setup.log 2>&1
  trap 'echo "RL SETUP FAILED line $LINENO"; touch /workspace/RL_SETUP_FAILED' ERR
  mkdir -p $CB && tar xzf $IN/code_rl.tgz --no-same-owner -C $CB && tar xzf $IN/data_rl.tgz --no-same-owner -C $CB
  (cd $CB && sha256sum -c --quiet $IN/data.sha)
  uv pip install -q -p $PY --reinstall-package torch torch --index-url https://download.pytorch.org/whl/cu128
  $PY -c "import torch; assert torch.cuda.is_available(); print(torch.__version__, torch.cuda.get_device_name(0))"
  cd $CB && ROYALE_RUNTIME=20261012-linux PYTHONPATH=$CB $PY -c "from pipeline.royale_runtime import activate; print(activate()['runtime_id'])"
  touch /workspace/RL_SETUP_OK; exit 0
fi
RUN=$2; O=/workspace/results/RLT_$RUN; mkdir -p $O
exec >> $O/run.log 2>&1
finish() { rc=$?; [ -s $O/SUMMARY.txt ] || echo "FAILED (exit $rc): see run.log / train.log" > $O/SUMMARY.txt; echo "exit_code=$rc" > $O/DONE; }
trap finish EXIT
cd $CB
export PYTHONPATH=$CB ROYALE_RUNTIME=20261012-linux ROYALE_HEROIW_FORM=normal OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 \
       PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1
echo "$(date -u +%T) train $RUN"
flock /workspace/cpu.lock $PY -m pipeline.rl_royale --config $IN/$RUN.yaml --run $RUN > $O/train.log 2>&1
cp scratchpad/gauntlet/L68/rl/$RUN/train_log.jsonl $O/
CK=icebow/data/bench/rl_royale/$RUN/${RUN}_u0020.pt
[ -f $CK ] || { echo "no final checkpoint $CK"; exit 3; }
sha256sum $CK > $O/final.sha
# Scoring runs the live condition (Hero IW + live press), like GAP_r1; ROYALE_HEROIW_FORM=hero is set by gap.py itself.
unset ROYALE_HEROIW_FORM
echo "$(date -u +%T) score final"
flock /workspace/cpu.lock $PY scratchpad/gauntlet/L74/gap/gap.py --ckpt $CK --out $O/score_final --arms D1,D0 --workers 25 > $O/score_final.log 2>&1
if [ "${3:-}" = init ]; then
  echo "$(date -u +%T) score init"
  flock /workspace/cpu.lock $PY scratchpad/gauntlet/L74/gap/gap.py --ckpt icebow/data/bench/rl_royale/newsim_base_main/newsim_base_main_u0060.pt \
    --out $O/score_init --arms D1,D0 --workers 25 > $O/score_init.log 2>&1
fi
{ echo "RLT $RUN: 20 updates from newsim_base_main_u0060 (r1 cfg; $(grep -c . $O/train_log.jsonl) log rows)"
  for d in $O/score_*; do echo "== $(basename $d)"; grep -E "^D[01]:" $d/SUMMARY.txt; done; } > $O/SUMMARY.txt
echo "$(date -u +%T) done"
