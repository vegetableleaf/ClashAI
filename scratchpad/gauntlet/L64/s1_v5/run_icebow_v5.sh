#!/bin/bash
# L64r chain, mirrors s1_v4/run_icebow_lat.sh. Waits for the corpus_v5 icebow drive to exit, then:
#   corpus_v5/icebow = corpus_v4/icebow (953) + every ok replay in corpus_v5_new/icebow (frames present)
#   -> s1_dataset_v5.npz -> v5lat x3 seeds -> eval on the v3 VAL rows (the same 6,133-row instrument as
#   18.17 / 19.84) -> ICEBOW_V5LAT_DONE.
# As soon as the engine slot frees, the hogeq never-driven drive (423 tags with attr_i; the other 55 of the 478
# are corpus_v3's known refusals, plays_ext.csv only) launches on 37031 in the background -- it is a 26 MB
# python + the emulator, so it rides alongside training.
cd /c/Users/benpe/ClashBot
set -e
O=scratchpad/gauntlet/L64/s1_v5
until grep -q DRIVE_V5_EXIT scratchpad/gauntlet/L64/drive_v5_icebow.out; do sleep 60; done
echo "drive exited $(date -u +%H:%M): $(grep DRIVE_V5_EXIT scratchpad/gauntlet/L64/drive_v5_icebow.out)"

python - <<'PY'
import json, pathlib
old = {r for r in json.load(open('scratchpad/gauntlet/L64/v5_tags_hogeq.json'))}
import csv
i1 = {r['replay_tag'] for r in csv.DictReader(open('hogeq/data/royaleapi/crawl2/plays_ext_i1.csv', encoding='utf-8'))}
keep = sorted(old & i1)
pathlib.Path('scratchpad/gauntlet/L64/v5_tags_hogeq_i1.json').write_text(json.dumps(keep), encoding='utf-8')
print('hogeq drive scope', len(keep), 'of', len(old))
PY
nohup research/ext/cr-native-sandbox/.venv/Scripts/python.exe research/sandbox_tools/replay_batch.py --crawl hogeq --plays-file plays_ext_i1.csv --tags scratchpad/gauntlet/L64/v5_tags_hogeq_i1.json --out scratchpad/gauntlet/ext/corpus_v5_new/hogeq --record-every 20 --record-plays --determinism-every 10 --port 37031 > scratchpad/gauntlet/L64/drive_v5_hogeq.out 2>&1 &
echo "hogeq drive launched pid $! $(date -u +%H:%M)"

python - <<'PY'
import shutil, pathlib, json
v4 = pathlib.Path('scratchpad/gauntlet/ext/corpus_v4/icebow'); new = pathlib.Path('scratchpad/gauntlet/ext/corpus_v5_new/icebow')
v5 = pathlib.Path('scratchpad/gauntlet/ext/corpus_v5/icebow'); v5.mkdir(parents=True, exist_ok=True)
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
print('corpus_v5/icebow: v4', len(a), 'new ok', len(ok), 'new without frames', nf, 'copied', n, 'total', len(list(v5.glob('replay_*.json'))))
PY
./icebow/.venv/Scripts/python.exe -m pipeline.dataset icebow --corpus scratchpad/gauntlet/ext/corpus_v5/icebow --out icebow/data/pipeline/s1_dataset_v5.npz > $O/dataset_icebow_v5.out 2>&1
tail -n 1 $O/dataset_icebow_v5.out | cut -c1-300
for s in 0 1 2; do
  ./icebow/.venv/Scripts/python.exe -m pipeline.train_s1 icebow --seed $s --epochs 20 --data icebow/data/pipeline/s1_dataset_v5.npz --tag v5lat --grid lattice --out-dir $O > $O/train_icebow_v5lat_s$s.log 2>&1
  tail -1 $O/train_icebow_v5lat_s$s.log | cut -c1-300
done
./icebow/.venv/Scripts/python.exe -m pipeline.eval_s1 icebow icebow/data/pipeline/s1_icebow_v5lat_s0.pt icebow/data/pipeline/s1_icebow_v5lat_s1.pt icebow/data/pipeline/s1_icebow_v5lat_s2.pt --data icebow/data/pipeline/s1_dataset.npz > $O/eval_v3val_icebow_v5lat.out 2>&1
tail -3 $O/eval_v3val_icebow_v5lat.out | cut -c1-300
echo "ICEBOW_V5LAT_DONE $(date -u +%H:%M)"
