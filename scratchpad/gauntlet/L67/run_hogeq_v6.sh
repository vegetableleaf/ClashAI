#!/bin/bash
# L67m: hogeq corpus_v6 = corpus_v5/hogeq + HF one-card-off decks (tesla <- cannon alias, MEASURED; HANDOFF 5cs.99 Q)
# Steps: pre-filter evo Elite Barbarians (engine blind spot) -> drive on both engine slots -> merge frames-bearing
# replays -> dataset -> 3 seeds v6lat, SEQUENTIAL (two trainers + detector crashed CUDA on the 8 GB card, 5cs.98)
# -> grade on the SAME v3 VAL instrument hogeq v5lat was graded on (s1_dataset.npz), so the numbers compare.
# Requires the engine booted from native PowerShell (scratchpad/gauntlet/L63/s0/_boot.ps1; Git Bash tar trap).
cd /c/Users/benpe/ClashBot
set -e
O=scratchpad/gauntlet/L67/s1_hogeq_v6
CR=scratchpad/gauntlet/ext/crawl_hf_hogeq
NEW=scratchpad/gauntlet/ext/corpus_v6_new/hogeq
V6=scratchpad/gauntlet/ext/corpus_v6/hogeq
ENGPY=research/ext/cr-native-sandbox/.venv/Scripts/python.exe
PY=./icebow/.venv/Scripts/python.exe
mkdir -p "$O" "$NEW"
ls hogeq/data/pipeline/ | grep -q s1_hogeq_v6lat && { echo "REFUSING: s1_hogeq_v6lat_* already exists"; exit 3; }

# 1. drop replays the engine cannot drive: either side holds evolved Elite Barbarians (card 26000043).
#    Measured on the v5 hogeq drive: 109 of 121 failures were exactly this.
$PY - <<'PY'
import csv, json, pathlib
cr = pathlib.Path('scratchpad/gauntlet/ext/crawl_hf_hogeq')
bad = set()
with (cr / 'battles.csv').open(encoding='utf-8', newline='') as h:
    for r in csv.DictReader(h):
        if 'elite-barbarians-ev1' in (r['team_deck'] + ',' + r['opponent_deck']).split(','):
            bad.add(r['replay_tag'])
tags = json.load(open(cr / 'tags.json', encoding='utf-8'))
ok = [t for t in tags if t not in bad]
(cr / 'tags_ok_a.json').write_text(json.dumps(ok[0::2]), encoding='utf-8')
(cr / 'tags_ok_b.json').write_text(json.dumps(ok[1::2]), encoding='utf-8')
print(f'mined {len(tags)}  evo-E-barb dropped {len(tags) - len(ok)}  to drive {len(ok)}')
PY

# 2. drive both slots in parallel
$ENGPY research/sandbox_tools/replay_batch.py --crawl $CR --tags $CR/tags_ok_a.json --out $NEW --record-every 20 --record-plays --port 37031 --determinism-every 0 > $O/drive_a.out 2>&1 &
$ENGPY research/sandbox_tools/replay_batch.py --crawl $CR --tags $CR/tags_ok_b.json --out $NEW --record-every 20 --record-plays --port 37032 --determinism-every 0 > $O/drive_b.out 2>&1 &
wait
echo "drive done $(date -u +%H:%M)"

# 3. merge: corpus_v5 + NEW frames-bearing replays (the same rule v5 and icebow v6 used)
$PY - <<'PY'
import shutil, pathlib, json
v5 = pathlib.Path('scratchpad/gauntlet/ext/corpus_v5/hogeq'); new = pathlib.Path('scratchpad/gauntlet/ext/corpus_v6_new/hogeq')
v6 = pathlib.Path('scratchpad/gauntlet/ext/corpus_v6/hogeq'); v6.mkdir(parents=True, exist_ok=True)
a = sorted(v5.glob('replay_*.json')); b = sorted(new.glob('replay_*.json'))
assert not (set(x.name for x in a) & set(x.name for x in b)), 'name collision v5 vs v6_new'
ok, nf = [], 0
for src in b:
    d = json.load(open(src, encoding='utf-8'))
    if 'frames' not in d or not d['frames']:
        nf += 1; continue
    ok.append(src)
for src in a + ok:
    dst = v6 / src.name
    if not dst.exists():
        shutil.copy2(src, dst)
print('corpus_v6/hogeq: v5', len(a), 'new ok', len(ok), 'new without frames', nf, 'total', len(list(v6.glob('replay_*.json'))))
PY

# 4. dataset (Deck.aliases maps the pros' cannon plays onto our tesla slot)
$PY -m pipeline.dataset hogeq --corpus $V6 --out hogeq/data/pipeline/s1_dataset_v6.npz > $O/dataset_hogeq_v6.out 2>&1
tail -n 1 $O/dataset_hogeq_v6.out | cut -c1-300

# 5. three seeds, sequential
for s in 0 1 2; do
  $PY -m pipeline.train_s1 hogeq --seed $s --epochs 20 --data hogeq/data/pipeline/s1_dataset_v6.npz --tag v6lat --grid lattice --out-dir $O > $O/train_hogeq_v6lat_s$s.log 2>&1
  tail -1 $O/train_hogeq_v6lat_s$s.log | cut -c1-300
done

# 6. grade v6lat AND re-grade v5lat on the identical v3 VAL instrument
$PY -m pipeline.eval_s1 hogeq hogeq/data/pipeline/s1_hogeq_v6lat_s0.pt hogeq/data/pipeline/s1_hogeq_v6lat_s1.pt hogeq/data/pipeline/s1_hogeq_v6lat_s2.pt --data hogeq/data/pipeline/s1_dataset.npz > $O/eval_v3val_hogeq_v6lat.out 2>&1
$PY -m pipeline.eval_s1 hogeq hogeq/data/pipeline/s1_hogeq_v5lat_s0.pt hogeq/data/pipeline/s1_hogeq_v5lat_s1.pt hogeq/data/pipeline/s1_hogeq_v5lat_s2.pt --data hogeq/data/pipeline/s1_dataset.npz > $O/eval_v3val_hogeq_v5lat_regrade.out 2>&1
tail -3 $O/eval_v3val_hogeq_v6lat.out | cut -c1-300
echo "RUN_DONE $(date -u +%H:%M)"
