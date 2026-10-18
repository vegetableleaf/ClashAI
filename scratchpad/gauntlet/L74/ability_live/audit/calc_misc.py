"""Small extra numbers from press_rows.json: pending wait, frozen-value buckets, already-dying frozen bodies, where the
bodies the rule counted went, per-match press counts by truth."""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = json.loads((HERE / 'press_rows.json').read_text())
for mark in ('CXXXVIII', 'CXXIV'):
    ok = [r for r in R if r['mark'] == mark and r.get('truth') == 'ready' and r.get('iw_pos')]
    full = [r for r in ok if not r['truncated']]
    print(f'\n== {mark}: {len(ok)} truth-ready presses, {len(full)} with a full 16 s window')
    w = sorted((r['cube_tick'] - r['effect_tick']) / 20 for r in ok if r.get('cube_tick') and r.get('effect_tick'))
    print('  pending wait (ability active -> cube) s: p50/p75/p90/max', w[len(w) // 2], w[3 * len(w) // 4],
          w[int(.9 * (len(w) - 1))], w[-1], '| > 1 s:', sum(x > 1 for x in w), '| > 3 s:', sum(x > 3 for x in w), '/', len(w))
    b = Counter('0' if r['frozen_value'] == 0 else '<2' if r['frozen_value'] < 2 else '2-4' if r['frozen_value'] < 4
                else '4-8' if r['frozen_value'] < 8 else '>=8' for r in full)
    print('  frozen elixir value per press:', dict(sorted(b.items())))
    for k in ('iw_clump', 'iw_wincon'):
        xs = [r for r in full if r['kind'] == k]
        print(f'   {k}: n={len(xs)} frozen value < 2: {sum(r["frozen_value"] < 2 for r in xs)}; median value',
              sorted(r['frozen_value'] for r in xs)[len(xs) // 2])
    fz = [f for r in full for f in r['frozen'].values()]
    dying = [f for f in fz if f['hp0'] / max(1, f['max_hp']) < .3 and f['died'] and f['died_by'] is not None
             and (f['last'] - f['first']) / 20 + f['died_by'] <= 1.0]
    print('  frozen bodies:', len(fz), '| already dying (<30% HP, dead within 1 s of the freeze start):', len(dying),
          f'value {sum(f["value"] for f in dying):.1f} of {sum(f["value"] for f in fz):.1f}')
    print('  frozen bodies on the enemy half at freeze start:', sum(not f['on_my_half'] for f in fz))
    # double presses in one deployment (same IW body) and the age gap between them
    by = Counter((r['log'], r.get('iw_gen')) for r in R if r['mark'] == mark and r.get('iw_gen'))
    print('  IW bodies with >1 press:', sum(v > 1 for v in by.values()))
