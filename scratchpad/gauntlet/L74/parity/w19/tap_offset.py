"""Own plays: where the live bodies first appear vs the tap point the harness replays them at (fights.read_match: the play's
confirmed 'intended' point). Per card and era: distance median / p90, and the mean offset (dx, dy) in our-side orientation.
  python tap_offset.py LIVE_DIR [GLOB]"""
import glob
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
from scratchpad.gauntlet.L74.parity.core import load_catalog  # noqa: E402

catalog, _ = load_catalog()
d, g = Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else 'live_play_*.jsonl'
off = defaultdict(list)
for p in sorted(glob.glob(str(d / g))):
    m, why = F.read_match(p)
    if m is None:
        continue
    era = 'L16' if Path(p).stem[10:23] >= '20261019_1402' else 'pre'
    tr = F.tracks(m['frames'])
    ky = next((bd['y'] for bd in m['frames'][0][1] if bd['tower'] and bd['side'] == m['side'] and bd['id'].endswith('K')), 0)
    flip = -1 if ky > 16000 else 1            # our-side orientation: +dy = toward the river
    used = set()
    for pl in m['plays']:
        c = next((c for c in catalog.values() if c['display_name'] == pl['name']), None)
        if not c or c.get('type') == 'spell' or pl['name'] in F.DIGGERS:
            continue
        cands = [r for r in tr.values() if r['side'] == m['side'] and (catalog.get(r['card_id']) or {}).get('display_name') == pl['name']
                 and pl['tick'] <= r['first'] <= pl['tick'] + 80 and r['id'] not in used]
        if not cands:
            continue
        t1 = min(r['first'] for r in cands)
        grp = [r for r in cands if r['first'] <= t1 + 2]
        used.update(r['id'] for r in grp)
        cx = statistics.fmean(r['x'] for r in grp); cy = statistics.fmean(r['y'] for r in grp)
        off[(pl['name'], era)].append((cx - pl['x'], (cy - pl['y']) * flip, math.hypot(cx - pl['x'], cy - pl['y'])))
print('card | era | n | median dist mt | p90 | mean dx | mean dy (toward river +) | share > 1000 mt')
for k in sorted(off):
    v = off[k]
    ds = sorted(x[2] for x in v)
    print(f'{k[0]} | {k[1]} | {len(v)} | {statistics.median(ds):.0f} | {ds[int(.9*len(ds))]:.0f} | '
          f'{statistics.fmean(x[0] for x in v):.0f} | {statistics.fmean(x[1] for x in v):.0f} | {sum(x > 1000 for x in ds)/len(ds):.3f}')
