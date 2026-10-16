"""Own Skeletons formation at birth: member offsets from the tap, live vs SIM (first frame each body is seen)."""
import json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture import capture, setup, F, ps
offs = Counter(); n = 0
paths = sorted(ps.LIVE.glob('live_play_2026101[5-9]_*.jsonl'))[::int(sys.argv[1])]
for p in paths:
    m, why = F.read_match(str(p))
    if not m: continue
    ctx = setup(p.stem); side = ctx['m']['side']
    res, _ = capture(p.stem, lambda f, a: a['name'] == 'Skeletons' and a['source'] == 'own_tap', ctx)
    for f, a, rows, st, r in res:
        if not rows: continue
        Ls, Ss = {}, {}
        for t, live, simb in rows:
            for b in live:
                if not b['tower'] and b['side'] == side and ctx['catalog'].get(b['card_id'], {}).get('display_name') == 'Skeletons' and b['id'] not in Ls and t > rows[0][0]:
                    Ls[b['id']] = (round(b['x'] - a['x']), round(b['y'] - a['y']))
            for b in simb:
                if not b['tower'] and b['side'] == side and b.get('name') == 'Skeletons' and b['id'] not in Ss and t > rows[0][0]:
                    Ss[b['id']] = (round(b['x'] - a['x']), round(b['y'] - a['y']))
        lo = sorted(v for v in Ls.values() if abs(v[0]) < 2000 and abs(v[1]) < 2000)
        so = sorted(v for v in Ss.values() if abs(v[0]) < 2000 and abs(v[1]) < 2000)
        if len(lo) == 3 and len(so) == 3:
            offs[(side, tuple(lo), tuple(so))] += 1; n += 1
print(n, 'plays with 3+3 members')
for k, v in offs.most_common(15):
    print(v, 'side', k[0], 'live', k[1], 'sim', k[2])
