#!/bin/bash
# icebow mirror of run_hogeq_v4.sh + run_hogeq_lat.sh: corpus_v4/icebow = corpus_v3/icebow + corpus_v3_i1r/icebow,
# dataset v4, then v3 --grid lattice x3 (baseline under the new convention) and v4 lattice x3, both evaluated on the v3 VAL rows.
cd /c/Users/benpe/ClashBot
set -e
O=scratchpad/gauntlet/L64/s1_v4
echo "start icebow $(date -u +%H:%M)"
python - <<'PY'
import shutil, pathlib, json
v3=pathlib.Path('scratchpad/gauntlet/ext/corpus_v3/icebow'); i1=pathlib.Path('scratchpad/gauntlet/ext/corpus_v3_i1r/icebow'); v4=pathlib.Path('scratchpad/gauntlet/ext/corpus_v4/icebow')
v4.mkdir(parents=True, exist_ok=True)
a=sorted(v3.glob('replay_*.json')); b=sorted(i1.glob('replay_*.json'))
assert not (set(x.name for x in a) & set(x.name for x in b))
assert 'frames' in json.load(open(b[0], encoding='utf-8')), 'i1r replay without frames'
n=0
for src in a+b:
    if not (v4/src.name).exists(): shutil.copy2(src, v4/src.name); n+=1
print('corpus_v4/icebow: v3', len(a), 'i1r', len(b), 'copied', n, 'total', len(list(v4.glob('replay_*.json'))))
PY
./icebow/.venv/Scripts/python.exe -m pipeline.dataset icebow --corpus scratchpad/gauntlet/ext/corpus_v4/icebow --out icebow/data/pipeline/s1_dataset_v4.npz > $O/dataset_icebow_v4.out 2>&1
tail -n 1 $O/dataset_icebow_v4.out | cut -c1-300
for s in 0 1 2; do
  ./icebow/.venv/Scripts/python.exe -m pipeline.train_s1 icebow --seed $s --epochs 20 --data icebow/data/pipeline/s1_dataset.npz --tag lat --grid lattice --out-dir $O > $O/train_icebow_lat_s$s.log 2>&1
  tail -1 $O/train_icebow_lat_s$s.log | cut -c1-300
done
./icebow/.venv/Scripts/python.exe -m pipeline.eval_s1 icebow icebow/data/pipeline/s1_icebow_lat_s0.pt icebow/data/pipeline/s1_icebow_lat_s1.pt icebow/data/pipeline/s1_icebow_lat_s2.pt --data icebow/data/pipeline/s1_dataset.npz > $O/eval_v3val_icebow_lat.out 2>&1
echo "ICEBOW_V3LAT_DONE $(date -u +%H:%M)"
for s in 0 1 2; do
  ./icebow/.venv/Scripts/python.exe -m pipeline.train_s1 icebow --seed $s --epochs 20 --data icebow/data/pipeline/s1_dataset_v4.npz --tag v4lat --grid lattice --out-dir $O > $O/train_icebow_v4lat_s$s.log 2>&1
  tail -1 $O/train_icebow_v4lat_s$s.log | cut -c1-300
done
./icebow/.venv/Scripts/python.exe -m pipeline.eval_s1 icebow icebow/data/pipeline/s1_icebow_v4lat_s0.pt icebow/data/pipeline/s1_icebow_v4lat_s1.pt icebow/data/pipeline/s1_icebow_v4lat_s2.pt --data icebow/data/pipeline/s1_dataset.npz > $O/eval_v3val_icebow_v4lat.out 2>&1
# floor reference through the same evaluate() so place_1t/place_dist exist for icebow v3 floor too
./icebow/.venv/Scripts/python.exe -m pipeline.eval_s1 icebow icebow/data/pipeline/s1_icebow_s0.pt icebow/data/pipeline/s1_icebow_s1.pt icebow/data/pipeline/s1_icebow_s2.pt --data icebow/data/pipeline/s1_dataset.npz > $O/eval_v3val_icebow_floor_place.out 2>&1
echo "ICEBOW_V4LAT_DONE $(date -u +%H:%M)"
