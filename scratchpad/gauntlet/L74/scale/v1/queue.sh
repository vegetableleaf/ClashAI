#!/bin/bash
# queue.sh -- P4-10M on pod 30408 (one 4090, 62 GB container cap), every step skipped when its output exists, so a
# restart = re-run this script:  cd /workspace/p4 && setsid nohup bash code/scratchpad/gauntlet/L74/scale/v1/queue.sh > queue.log 2>&1 &
# Stop: touch /workspace/p4/STOP (checked between steps); a running step is stopped by its exact PID.
set -u
W=/workspace/p4; V=$W/code/scratchpad/gauntlet/L74/scale/v1; PY=/workspace/venvf16/bin/python
cd $W
step() { [ -f $W/STOP ] && { echo "$(date -u +%FT%TZ) STOP"; exit 0; }; echo "$(date -u +%FT%TZ) $*"; gpu_free; }
# the GPU is shared (other agents run srv_bench there): wait until >= 18 GB is free on two checks 60 s apart
gpu_free() { local ok=0; while [ $ok -lt 2 ]; do f=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits -i 0)
  if [ "$f" -ge 18000 ]; then ok=$((ok + 1)); else ok=0; echo "$(date -u +%FT%TZ) gpu busy ($f MiB free)"; fi; sleep 60; done; }
# 1. memory tables (identity RD1 == slot re-drive already checked on 33308: 241/241 shards)
if [ ! -f data/mix_v1_memory.npz ]; then step memory
  PYTHONPATH=$W/pylib $PY $V/build_mix_memory.py --mix data/mix_v1.npz --v32-memory data/gen_dataset_v32_fv5_memory_v1.npz \
    --rd data/rd --slot data/slot --check-shards 0 --out data/mix_v1_memory.npz > data/build_mix_memory.log 2>&1 || exit 1; fi
# 2. icebow subset (+ its memory tables)
if [ ! -f data/ice_v1.npz ]; then step subset
  $PY $V/make_subset.py --mix data/mix_v1.npz --memory data/mix_v1_memory.npz --out data/ice_v1.npz > data/ice_v1.log 2>&1 || exit 1; fi
# 3. trainer smoke: the step trainer with --memory alone (300 steps, fv6 + memory v2, 10.6 M trunk) on the mix
if ! grep -q FINAL runs/base_smoke/train.out 2>/dev/null; then step smoke
  EVERY=300 EROWS=5000 bash $V/run_base.sh pre $W/runs/base_smoke 300; grep -q FINAL runs/base_smoke/train.out || exit 1; fi
# 4. base pretrain: 1 epoch of the mix's train rows (13.1 M / 256)
if ! grep -q FINAL runs/base_pre/train.out 2>/dev/null; then step base_pre
  bash $V/run_base.sh pre $W/runs/base_pre ${PRE_STEPS:-51000}; fi
# 5. icebow fine-tune from the pretrain's best checkpoint: ~2 epochs of the icebow train rows
if ! grep -q FINAL runs/base_ice/train.out 2>/dev/null; then step base_ice
  N=$($PY -c "import json,numpy as np;print(json.loads(str(np.load('data/ice_v1.npz')['meta']))['subset']['split_counts']['0'])")
  bash $V/run_base.sh ice $W/runs/base_ice $(( N * 2 / 256 )) $W/runs/base_pre/opp_base_pre_s0.pt; fi
# 6. held-out evals: base (pre, ice) and CLXIII on the same rows
for C in base_ice/opp_base_ice_s0 base_pre/opp_base_pre_s0; do
  [ -f runs/${C%%/*}/eval.json ] || { step eval $C; $PY $V/scale_eval_v1.py $W/code runs/$C.pt data/mix_v1.npz runs/${C%%/*}/eval.json \
    --memory-tables data/mix_v1_memory.npz --mmap-cache-dir data/cache_ev > runs/${C%%/*}/eval.out 2>&1; rm -rf data/cache_ev; }; done
[ -f runs/clxiii_eval.json ] || { step eval clxiii; $PY $V/scale_eval_v1.py $W/code data/ICEBOW_Mark_CLXIII_NOLEAK.pt data/mix_v1.npz \
  runs/clxiii_eval.json --mmap-cache-dir data/cache_ev > runs/clxiii_eval.out 2>&1; rm -rf data/cache_ev; }
# 7. curve v1 (1 epoch each = curve v0's sample count; v0 = 4 epochs of 3.17 M)
for R in "m10 320 7 0" "m2 160 4 0" "m5 224 6 0" "m20 384 10 0" "m10 320 7 1"; do set -- $R
  [ -f runs/${1}_s$4/eval.json ] || { step curve $R; bash $V/run_size_v1.sh $1 $2 $3 $4 1; }; done
step DONE
