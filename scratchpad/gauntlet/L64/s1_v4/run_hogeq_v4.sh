#!/bin/bash
# corpus_v4/hogeq = corpus_v3/hogeq + corpus_v3_i1r/hogeq (i=1 half, rotated, driven with v3's flags), then S1 x3 seeds
# on the v4 dataset (ONE change vs L64d-f: the corpus), checkpoints tagged v4, evaluated on the v3 VAL rows.
cd /c/Users/benpe/ClashBot
set -e
D=scratchpad/gauntlet/L64/s1_v4
python - <<'PY'
import shutil, pathlib
v3=pathlib.Path('scratchpad/gauntlet/ext/corpus_v3/hogeq'); i1=pathlib.Path('scratchpad/gauntlet/ext/corpus_v3_i1r/hogeq'); v4=pathlib.Path('scratchpad/gauntlet/ext/corpus_v4/hogeq')
v4.mkdir(parents=True, exist_ok=True)
a=sorted(v3.glob('replay_*.json')); b=sorted(i1.glob('replay_*.json'))
assert not (set(x.name for x in a) & set(x.name for x in b))
n=0
for src in a+b:
    if not (v4/src.name).exists(): shutil.copy2(src, v4/src.name); n+=1
print('corpus_v4/hogeq: v3', len(a), 'i1r', len(b), 'copied', n, 'total', len(list(v4.glob('replay_*.json'))))
PY
./icebow/.venv/Scripts/python.exe -m pipeline.dataset hogeq --corpus scratchpad/gauntlet/ext/corpus_v4/hogeq --out hogeq/data/pipeline/s1_dataset_v4.npz > $D/dataset_hogeq_v4.out 2>&1
tail -n 1 $D/dataset_hogeq_v4.out
for s in 0 1 2; do
  ./icebow/.venv/Scripts/python.exe -m pipeline.train_s1 hogeq --seed $s --epochs 20 --data hogeq/data/pipeline/s1_dataset_v4.npz --tag v4 --out-dir $D > $D/train_hogeq_v4_s$s.log 2>&1
done
./icebow/.venv/Scripts/python.exe -m pipeline.eval_s1 hogeq hogeq/data/pipeline/s1_hogeq_v4_s0.pt hogeq/data/pipeline/s1_hogeq_v4_s1.pt hogeq/data/pipeline/s1_hogeq_v4_s2.pt hogeq/data/pipeline/s1_hogeq_s0.pt hogeq/data/pipeline/s1_hogeq_s1.pt hogeq/data/pipeline/s1_hogeq_s2.pt --data hogeq/data/pipeline/s1_dataset.npz > $D/eval_v3val_hogeq.out 2>&1
./icebow/.venv/Scripts/python.exe -m pipeline.eval_s1 hogeq hogeq/data/pipeline/s1_hogeq_v4_s0.pt hogeq/data/pipeline/s1_hogeq_v4_s1.pt hogeq/data/pipeline/s1_hogeq_v4_s2.pt hogeq/data/pipeline/s1_hogeq_s0.pt hogeq/data/pipeline/s1_hogeq_s1.pt hogeq/data/pipeline/s1_hogeq_s2.pt --data hogeq/data/pipeline/s1_dataset_v4.npz > $D/eval_v4val_hogeq.out 2>&1
echo HOGEQ_V4_DONE
