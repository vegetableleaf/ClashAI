"""Index + cache the graded live ladder matches of the Marks W5 studies (CXXXVIII, CLIII, CLIX, CLX) into L74/habits/cache
(same compact format as habits/build_cache.py; already-built pickles are reused).  -> investment/index.json
    nice -n 19 python build_live.py        (single process; laptop-safe)"""
import json
import pickle
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
L74 = HERE.parent
REPO = L74.parents[2]
sys.path.insert(0, str(L74 / 'habits'))
sys.path.insert(0, str(L74 / 'monitor'))
import build_cache as B  # noqa: E402
import card_use  # noqa: E402

WANT = ('ICEBOW Mark CXXXVIII:', 'ICEBOW Mark CLIII:', 'ICEBOW Mark CLIX:', 'ICEBOW Mark CLX:')
reg = json.load(open(L74 / 'models/registry.json'))
sha2mark = {f['sha256']: m['name'] for m in reg['marks'] for f in m.get('files', []) if f.get('sha256')}
res = card_use.results()
idx = {}
for p in sorted((REPO / 'scratchpad/gauntlet/L68/live_reader').glob('live_play_2026*.jsonl')):
    if p.name not in res:
        continue
    with open(p, 'rb') as f:
        try:
            j = json.loads(f.readline())
        except ValueError:
            continue
    if j.get('event') != 'start' or j.get('dry_run'):
        continue
    mark = sha2mark.get(j.get('ckpt_sha256'), '')
    if mark.startswith(WANT):
        idx[p.name] = dict(mark=mark, result=res[p.name][0], tro=res[p.name][1])
json.dump(idx, open(HERE / 'index.json', 'w'), indent=0)
from collections import Counter  # noqa: E402
print(Counter(v['mark'] for v in idx.values()))
C = L74 / 'habits/cache'
todo = [(n, v) for n, v in sorted(idx.items()) if not (C / (Path(n).stem + '.pkl')).exists()]
print(len(todo), 'to build', flush=True)
for i, (n, v) in enumerate(todo):
    try:
        m = B.livelog.read(B.LOGS / n)
    except Exception as e:  # noqa: BLE001 -- a broken log is skipped and named
        print('FAIL', n, repr(e)[:200], flush=True)
        continue
    if m is None:
        print('NOFRAMES', n, flush=True)
        continue
    tmp = C / (Path(n).stem + '.tmp')
    pickle.dump(B.compact(m, dict(v, log=n)), open(tmp, 'wb'))
    tmp.replace(tmp.with_suffix('.pkl'))
    if i % 25 == 0:
        print(i, n, flush=True)
print('done', flush=True)
