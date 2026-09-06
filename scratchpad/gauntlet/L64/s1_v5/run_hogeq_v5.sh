#!/bin/bash
# L64t chain, mirrors run_icebow_v5.sh for hogeq. Waits for (1) the hogeq drive (msys pid 546066) to exit and
# (2) ICEBOW_V5LAT_DONE -- the box has 2.7 GB free under one trainer, a second one would not fit. Then:
#   corpus_v5/hogeq = corpus_v4/hogeq (463) + every frames-bearing replay in corpus_v5_new/hogeq
#   -> s1_dataset_v5.npz -> v5lat x3 seeds -> eval on the hogeq v3 VAL rows (the 21.00 / 22.56 instrument)
#   -> HOGEQ_V5LAT_DONE.
cd /c/Users/benpe/ClashBot
set -e
O=scratchpad/gauntlet/L64/s1_v5
until [ -z "$(ps | awk '$1==546066')" ]; do sleep 60; done
echo "hogeq drive exited $(date -u +%H:%M): $(tail -c 400 scratchpad/gauntlet/L64/drive_v5_hogeq.out | tr -d '\n' | cut -c1-300)"
until grep -q ICEBOW_V5LAT_DONE $O/run_icebow_v5.out; do sleep 60; done
echo "icebow chain done $(date -u +%H:%M)"
ls hogeq/data/pipeline/ | grep -q s1_hogeq_v5lat && { echo "REFUSING: s1_hogeq_v5lat_* already exists"; exit 3; }

python - <<'PY'
import shutil, pathlib, json
v4 = pathlib.Path('scratchpad/gauntlet/ext/corpus_v4/hogeq'); new = pathlib.Path('scratchpad/gauntlet/ext/corpus_v5_new/hogeq')
v5 = pathlib.Path('scratchpad/gauntlet/ext/corpus_v5/hogeq'); v5.mkdir(parents=True, exist_ok=True)
a = sorted(v4.glob('replay_*.json')); b = sorted(new.glob('replay_*.json'))
assert not (set(x.name for x in a) & set(x.name for x in b)), 'name collision v4 vs v5_new'
nf = 0; ok = []
for src in b:
    d = json.load(open(src, encoding='utf-8'))
    if 'frames' not in d or not d['frames']:
        nf += 1; continue
    ok.append(src)
n = 0
for src in a + ok:
    if not (v5 / src.name).exists():
        shutil.copy2(src, v5 / src.name); n += 1
print('corpus_v5/hogeq: v4', len(a), 'new ok', len(ok), 'new without frames', nf, 'copied', n, 'total', len(list(v5.glob('replay_*.json'))))
PY
./icebow/.venv/Scripts/python.exe -m pipeline.dataset hogeq --corpus scratchpad/gauntlet/ext/corpus_v5/hogeq --out hogeq/data/pipeline/s1_dataset_v5.npz > $O/dataset_hogeq_v5.out 2>&1
tail -n 1 $O/dataset_hogeq_v5.out | cut -c1-300
for s in 0 1 2; do
  ./icebow/.venv/Scripts/python.exe -m pipeline.train_s1 hogeq --seed $s --epochs 20 --data hogeq/data/pipeline/s1_dataset_v5.npz --tag v5lat --grid lattice --out-dir $O > $O/train_hogeq_v5lat_s$s.log 2>&1
  tail -1 $O/train_hogeq_v5lat_s$s.log | cut -c1-300
done
./icebow/.venv/Scripts/python.exe -m pipeline.eval_s1 hogeq hogeq/data/pipeline/s1_hogeq_v5lat_s0.pt hogeq/data/pipeline/s1_hogeq_v5lat_s1.pt hogeq/data/pipeline/s1_hogeq_v5lat_s2.pt --data hogeq/data/pipeline/s1_dataset.npz > $O/eval_v3val_hogeq_v5lat.out 2>&1
tail -3 $O/eval_v3val_hogeq_v5lat.out | cut -c1-300
echo "HOGEQ_V5LAT_DONE $(date -u +%H:%M)"
