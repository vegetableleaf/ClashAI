#!/bin/bash
# L67c: corpus_v6 = corpus_v5/icebow + frames-bearing HF replays (same rule as v5), dataset, 3 seeds v6lat, v3 VAL clean + degraded.
cd /c/Users/benpe/ClashBot
set -e
O=scratchpad/gauntlet/L67/s1_v6
mkdir -p $O
until grep -q DRIVE_DONE scratchpad/gauntlet/L67/drive_v6_a.out; do sleep 60; done
echo "drive done $(date -u +%H:%M)"
ls icebow/data/pipeline/ | grep -q s1_icebow_v6lat && { echo "REFUSING: s1_icebow_v6lat_* already exists"; exit 3; }

./icebow/.venv/Scripts/python.exe - <<'PY'
import shutil, pathlib, json
v5 = pathlib.Path('scratchpad/gauntlet/ext/corpus_v5/icebow'); new = pathlib.Path('scratchpad/gauntlet/ext/corpus_v6_new/icebow')
v6 = pathlib.Path('scratchpad/gauntlet/ext/corpus_v6/icebow'); v6.mkdir(parents=True, exist_ok=True)
a = sorted(v5.glob('replay_*.json')); b = sorted(new.glob('replay_*.json'))
assert not (set(x.name for x in a) & set(x.name for x in b)), 'name collision v5 vs v6_new'
nf = 0; ok = []; mism = 0
for src in b:
    d = json.load(open(src, encoding='utf-8'))
    if 'frames' not in d or not d['frames']:
        nf += 1; continue
    ok.append(src)
    if not d.get('crowns_match', True): mism += 1
n = 0
for src in a + ok:
    if not (v6 / src.name).exists():
        shutil.copy2(src, v6 / src.name); n += 1
print('corpus_v6/icebow: v5', len(a), 'new ok', len(ok), 'new without frames', nf, 'new crowns mismatch', mism, 'copied', n, 'total', len(list(v6.glob('replay_*.json'))))
PY
./icebow/.venv/Scripts/python.exe -m pipeline.dataset icebow --corpus scratchpad/gauntlet/ext/corpus_v6/icebow --out icebow/data/pipeline/s1_dataset_v6.npz > $O/dataset_icebow_v6.out 2>&1
tail -n 1 $O/dataset_icebow_v6.out | cut -c1-300
for s in 0 1 2; do
  ./icebow/.venv/Scripts/python.exe -m pipeline.train_s1 icebow --seed $s --epochs 20 --data icebow/data/pipeline/s1_dataset_v6.npz --tag v6lat --grid lattice --out-dir $O > $O/train_icebow_v6lat_s$s.log 2>&1
  tail -1 $O/train_icebow_v6lat_s$s.log | cut -c1-300
done
C="icebow/data/pipeline/s1_icebow_v6lat_s0.pt icebow/data/pipeline/s1_icebow_v6lat_s1.pt icebow/data/pipeline/s1_icebow_v6lat_s2.pt"
./icebow/.venv/Scripts/python.exe -m pipeline.eval_s1 icebow $C --data icebow/data/pipeline/s1_dataset.npz > $O/eval_v3val_icebow_v6lat.out 2>&1
tail -3 $O/eval_v3val_icebow_v6lat.out | cut -c1-300
./icebow/.venv/Scripts/python.exe -m pipeline.eval_s1 icebow $C --data scratchpad/gauntlet/L67/s1_dataset_v3_degraded_s0.npz > $O/eval_v3degraded_icebow_v6lat.out 2>&1
tail -3 $O/eval_v3degraded_icebow_v6lat.out | cut -c1-300
echo "ICEBOW_V6LAT_DONE $(date -u +%H:%M)"
