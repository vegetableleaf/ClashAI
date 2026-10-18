"""Index of graded live icebow ladder matches: log name -> Mark (start ckpt_sha256 via the registry), result, trophies.
   python index.py  -> index.json"""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / 'scratchpad/gauntlet/L74/monitor'))
import card_use

reg = json.load(open(REPO / 'scratchpad/gauntlet/L74/models/registry.json'))
sha2mark = {f['sha256']: m['name'] for m in reg['marks'] for f in m.get('files', []) if f.get('sha256')}
res = card_use.results()
out = {}
for p in sorted((REPO / 'scratchpad/gauntlet/L68/live_reader').glob('live_play_2026*.jsonl')):
    if p.name not in res:
        continue
    with open(p, 'rb') as f:
        head = f.readline()
    try:
        j = json.loads(head)
    except ValueError:
        continue
    if j.get('event') != 'start' or j.get('dry_run'):
        continue
    out[p.name] = dict(mark=sha2mark.get(j.get('ckpt_sha256'), Path(j.get('ckpt') or '?').name), result=res[p.name][0],
                       tro=res[p.name][1], mb=round(p.stat().st_size / 1e6, 1))
json.dump(out, open(HERE / 'index.json', 'w'), indent=0)
from collections import Counter
c = Counter(v['mark'] for v in out.values())
for k, n in c.most_common(15):
    rs = [v for v in out.values() if v['mark'] == k]
    print(n, k, 'win %.3f' % (sum(v['result'] == 'WIN' for v in rs) / n), 'MB %.0f' % sum(v['mb'] for v in rs),
          min(n_ for n_, v in out.items() if v['mark'] == k)[10:25], max(n_ for n_, v in out.items() if v['mark'] == k)[10:25])
